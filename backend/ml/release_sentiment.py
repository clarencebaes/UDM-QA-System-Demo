"""Compare a versioned SVM and semantic policy without overwriting legacy models.

Survey annotations are provisional, except author-confirmed regression examples.
Metrics are diagnostic; baseline respondent independence is not established.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import joblib
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import classification_report, f1_score

from ml.aspect_transition import families, checked_output
from ml.feedback_semantics import policy_decision, general_sentiment, unsupported_feedback, POLICY_VERSION
from ml.review_workflow import key, similar, digest, snapshot
from ml.sentiment_v3 import build_candidate, code_fingerprint
from ml.train import load_rows, MODEL_DIR

LABELS = ("positive", "negative", "constructive")


from ml.sentiment_decision import decide


def metrics(rows, predictions):
    truth = [r["sentiment"] for r in rows]
    predictions = [p or "unclassified" for p in predictions]
    matrix = np.zeros((3,4),dtype=int)
    for target,prediction in zip(truth,predictions):
        matrix[LABELS.index(target),LABELS.index(prediction) if prediction in LABELS else 3] += 1
    return {"n": len(rows), "labels": LABELS, "distribution": dict(Counter(truth)),
            "macro_f1": f1_score(truth,predictions,labels=LABELS,average="macro",zero_division=0),
            "per_class": classification_report(truth,predictions,labels=LABELS,output_dict=True,zero_division=0),
            "prediction_columns": [*LABELS,"unclassified (abstention, not a fourth trained class)"],
            "confusion_matrix": matrix.tolist(), "abstentions": predictions.count("unclassified"),
            "representative_misclassifications": [{"id":r["id"],"text":r["text"],"expected":r["sentiment"],"predicted":p}
                for r,p in zip(rows,predictions) if p!=r["sentiment"]][:20]}


def release(source, annotations, confirmed, out):
    source, annotations, confirmed = map(Path,(source,annotations,confirmed))
    raw = json.loads(source.read_text(encoding="utf-8"))["records"]
    prior = {str(r["id"]):r for r in json.loads(annotations.read_text(encoding="utf-8"))}
    confirmations = {key(r["text"]):r["sentiment"] for r in json.loads(confirmed.read_text(encoding="utf-8"))}
    found = set()
    real = []
    for row in raw:
        old = prior.get(str(row["id"]))
        if old is None or old["text"] != row["text"]:
            raise ValueError("New/changed raw text needs separate annotation review")
        k = key(row["text"])
        if k in confirmations: found.add(k)
        label = confirmations.get(k) or general_sentiment(row["text"]) or old["sentiment"]
        if not label or unsupported_feedback(row["text"]) or policy_decision(row["text"])["reason"]=="ambiguous_general_feedback": continue
        real.append({**row,"id":str(row["id"]),"sentiment":label,"confirmed":k in confirmations})
    if set(confirmations)-found:
        raise ValueError("Some author-confirmed comments were not found in the source")
    grouped = families(real)
    for row, group in zip(real,grouped):row["family"]=group
    unique = {}
    for row in real:
        k = key(row["text"])
        if k in unique and row["sentiment"]!=unique[k]["sentiment"]:
            raise ValueError("Conflicting exact duplicate labels")
        unique.setdefault(k,row)
    real = list(unique.values())
    legacy = load_rows()
    legacy_keys = [key(r[0]) for r in legacy]
    split = {}
    for group in set(grouped):
        use=[r for r in real if r["family"]==group]
        material="\n".join(sorted(key(r["text"]) for r in use))
        bucket=int(hashlib.sha256(material.encode()).hexdigest()[:8],16)%10
        assigned="holdout" if bucket==0 else "validation" if bucket in (1,2) else "train"
        # Provided regression corrections are training feedback, never independent tests.
        if any(r["confirmed"] for r in use) or any(similar(key(r["text"]),k) for r in use for k in legacy_keys):
            assigned="train"
        split[group]=assigned
    for row in real:row["split"]=split[row["family"]]
    training=[r for r in real if r["split"]=="train"]
    selected={key(r["text"]):r for r in training}
    conflicts=[]
    for i,(text,aspect,sentiment,language) in enumerate(legacy):
        k=key(text)
        if k in selected:
            if selected[k]["sentiment"]!=sentiment:
                conflicts.append({"text":text,"legacy":sentiment,"proposed":selected[k]["sentiment"]})
                if not selected[k]["confirmed"]:raise ValueError("Unconfirmed legacy label conflict")
            continue
        selected[k]={"id":f"legacy-{i}","text":text,"sentiment":sentiment,
                     "source":"legacy-seed-corpus","respondent":"", "split":"train"}
    train=list(selected.values())
    calibration_groups=families(train)
    X=[r["text"] for r in train];y=[r["sentiment"] for r in train]
    folds=None
    for count in (3,2):
        possible=list(StratifiedGroupKFold(n_splits=count,shuffle=True,random_state=42).split(X,y,calibration_groups))
        if all(set(np.asarray(y)[a])==set(LABELS) for a,b in possible):
            folds=possible;break
    if folds is None:raise ValueError("Insufficient class/group coverage for independent calibration folds")
    out=checked_output(out)
    hashes=snapshot(out)
    shutil.copy2(MODEL_DIR/"aspect_v2.joblib",out/"baseline"/"aspect_v2.joblib")
    baseline=joblib.load(out/"baseline"/"sentiment_nb.joblib")
    candidate=build_candidate(folds).fit(X,y)
    report={"policy_version":POLICY_VERSION,"independent_ground_truth":False,
            "limitations":"Survey labels are provisional except supplied corrections; baseline respondent independence unverified. Confirmed regression cases are in training, not test accuracy.",
            "source_sha256":digest(source),"annotations_sha256":digest(annotations),"confirmed_sha256":digest(confirmed),
            "training_rows":len(train),"training_distribution":dict(Counter(y)),"calibration_folds":len(folds),
            "legacy_conflicts":conflicts,"real_split_distribution":{s:dict(Counter(r["sentiment"] for r in real if r["split"]==s)) for s in ("train","validation","holdout")}}
    validation=[r for r in real if r["split"]=="validation"]
    if not validation:raise ValueError("No validation groups available")
    options={"baseline_with_policy":baseline,"retrained_svm_with_policy":candidate}
    validation_reports={name:metrics(validation,[decide(m,r["text"])["label"] for r in validation]) for name,m in options.items()}
    choice=max(options,key=lambda name:validation_reports[name]["macro_f1"])
    model=options[choice]
    report["selected"]=choice
    report["validation"]={"baseline_model":metrics(validation,list(map(str,baseline.predict([r["text"] for r in validation])))),**validation_reports}
    holdout=[r for r in real if r["split"]=="holdout"]
    report["holdout"]={"baseline_model":metrics(holdout,list(map(str,baseline.predict([r["text"] for r in holdout])))),
                       "selected_hybrid":metrics(holdout,[decide(model,r["text"])["label"] for r in holdout])} if holdout else {"n":0,"not_evaluable":True}
    version="sentiment-v3-"+hashlib.sha256((digest(source)+digest(confirmed)+choice+code_fingerprint()+joblib.hash(model)).encode()).hexdigest()[:12]
    joblib.dump({"version":version,"model":model,"policy_version":POLICY_VERSION,"selected":choice,
                 "status":"experimental-provisional-data","source_sha256":digest(source),"code_fingerprint":code_fingerprint()},out/"sentiment_v3.joblib")
    (out/"frozen-real-split.json").write_text(json.dumps(real,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"comparison.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    assert hashes=={name:digest(MODEL_DIR/name) for name in hashes}
    assert digest(MODEL_DIR/"aspect_v2.joblib")==digest(out/"baseline"/"aspect_v2.joblib")
    return out


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True);p.add_argument("--annotations",type=Path,required=True)
    p.add_argument("--confirmed",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();print(release(a.source,a.annotations,a.confirmed,a.out))
