"""Explicit, backed-up derived-label migration. Never changes raw Feedback fields.

Run only after reviewing the candidate and backing up the intended database.
The backup includes personal-data-linked IDs: keep it outside version control.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from sqlalchemy import create_engine, select, delete, DateTime
from sqlalchemy.orm import Session
from app.config import Settings
from app.models import (Feedback, FeedbackLabel, FeedbackAspectRun, FeedbackAspectTag,
                        Aspect, Threshold, InterventionRule, Alert)
from app.seed import seed_aspect_catalog
from app.services.aspect_model import load_aspect_model, infer_aspects, runtime_version
from app.services.sentiment_model import load_sentiment_model, predict_sentiment, sentiment_status
from app.services.alerts import evaluate_thresholds


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def records(db, model):
    return [dict(r) for r in db.execute(select(model.__table__).order_by(*model.__table__.primary_key)).mappings()]


def restore(db, backup_path):
    """Restore only backed-up derived rows. Keep later submissions and QUAD edits."""
    backup=json.loads(Path(backup_path).read_text(encoding='utf-8'))
    raw_ids=set(backup['raw_ids']);ids=backup['affected_ids']
    if fingerprint([r for r in records(db,Feedback) if r['id'] in raw_ids])!=backup['raw_sha256']:
        raise ValueError('Original raw records differ; investigate before restoring labels')
    for model in (FeedbackAspectTag,FeedbackAspectRun,FeedbackLabel):
        db.execute(delete(model).where(model.feedback_id.in_(ids)))
    for model in (FeedbackLabel,FeedbackAspectRun,FeedbackAspectTag):
        rows=[r for r in backup['tables'][model.__tablename__] if r['feedback_id'] in ids]
        for row in rows:
            for column in model.__table__.columns:
                if isinstance(column.type,DateTime) and row.get(column.name):
                    row[column.name]=datetime.fromisoformat(row[column.name])
        if rows:db.execute(model.__table__.insert(),rows)
    db.commit()
    for threshold in db.query(Threshold).all():evaluate_thresholds(db,threshold.aspect_id)
    return {'restored_comments':len(ids),'raw_unchanged':True,'later_submissions_preserved':True}


def migrate(db, backup_path):
    backup_path=Path(backup_path)
    if backup_path.exists():raise ValueError('Backup must be a new file; never overwrite it')
    load_aspect_model();load_sentiment_model()
    if sentiment_status()['sentiment_model_version'].startswith('legacy'):
        raise ValueError('Reviewed v3 artifact must be installed before migration')
    raw=records(db,Feedback)
    affected=[r for r in raw if (r['comment'] or '').strip()]
    ids=[r['id'] for r in affected]
    backup={'created_at':datetime.now(timezone.utc).isoformat(), 'raw_count':len(raw),'raw_sha256':fingerprint(raw),
            'raw_ids':[r['id'] for r in raw], 'affected_ids':ids,
            'tables':{m.__tablename__:records(db,m) for m in
                (FeedbackLabel,FeedbackAspectRun,FeedbackAspectTag,Aspect,Threshold,InterventionRule,Alert)},
            'new_sentiment':sentiment_status(), 'new_aspect_version':runtime_version()}
    backup_path.parent.mkdir(parents=True,exist_ok=True)
    with backup_path.open('x',encoding='utf-8') as stream:json.dump(backup,stream,ensure_ascii=False,default=str,indent=2)
    # Compute before changing database rows; repeated text is inferred once.
    cache={}
    for r in affected:
        text=r['comment']
        if text not in cache:cache[text]=(predict_sentiment(text,None),infer_aspects(text))
    seed_aspect_catalog(db);db.flush()
    definitions={a.code:a.id for a in db.query(Aspect).all()}
    previous={r['feedback_id']:r for r in backup['tables']['feedback_labels']}
    db.execute(delete(FeedbackAspectTag).where(FeedbackAspectTag.feedback_id.in_(ids)))
    db.execute(delete(FeedbackAspectRun).where(FeedbackAspectRun.feedback_id.in_(ids)))
    db.execute(delete(FeedbackLabel).where(FeedbackLabel.feedback_id.in_(ids)))
    runs=[];tags=[];labels=[];ledger=[]
    for r in affected:
        decision,topics=cache[r['comment']];old=previous.get(r['id'])
        runs.append(dict(feedback_id=r['id'],model_version=runtime_version(),status='assigned' if topics else 'not_applicable'))
        for code,score in topics:tags.append(dict(feedback_id=r['id'],aspect_id=definitions[code],score=score))
        if decision['label']:
            if old:
                label={**old,'sentiment':decision['label'],'sentiment_confidence':decision['model_probability']}
            else:
                if not topics:raise ValueError('Meaningful sentiment requires an identifiable or general topic')
                label=dict(feedback_id=r['id'],aspect_id=definitions[topics[0][0]],aspect_confidence=topics[0][1],
                           aspect_source='model',sentiment=decision['label'],sentiment_confidence=decision['model_probability'])
            labels.append(label)
        ledger.append(dict(id=r['id'],before=old['sentiment'] if old else None,after=decision['label'],reason=decision['reason'],aspects=[c for c,s in topics]))
    if runs:db.execute(FeedbackAspectRun.__table__.insert(),runs)
    if tags:db.execute(FeedbackAspectTag.__table__.insert(),tags)
    # Existing label IDs are preserved. Insert existing and newly classified rows separately.
    for group in ([r for r in labels if 'id' in r],[r for r in labels if 'id' not in r]):
        if group:db.execute(FeedbackLabel.__table__.insert(),group)
    after=[r for r in records(db,Feedback) if r['id'] in set(backup['raw_ids'])]
    if fingerprint(after)!=backup['raw_sha256']:raise ValueError('Raw data changed; transaction must roll back')
    db.commit()
    for threshold in db.query(Threshold).all():evaluate_thresholds(db,threshold.aspect_id)
    summary=dict(comments=len(affected),raw_unchanged=True,aspects=len(tags),
                 sentiments=dict(Counter(r['after'] or 'unclassified' for r in ledger)),
                 changed=sum(r['before']!=r['after'] for r in ledger),sentiment_model=sentiment_status())
    backup_path.with_suffix('.result.json').write_text(json.dumps(dict(summary=summary,ledger=ledger),indent=2),encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file',required=True);p.add_argument('--backup',type=Path,required=True)
    action=p.add_mutually_exclusive_group(required=True)
    action.add_argument('--apply-reviewed-labels',action='store_true')
    action.add_argument('--restore-derived-labels',action='store_true')
    args=p.parse_args();cfg=Settings(_env_file=args.env_file)
    engine=create_engine(cfg.database_url,connect_args=cfg.connect_args)
    with Session(engine) as db:print(json.dumps((restore if args.restore_derived_labels else migrate)(db,args.backup)))
