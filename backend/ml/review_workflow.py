"""Non-destructive annotation staging and fixed-family candidate comparison.
Run python -m ml.review_workflow --help. Production files are never written.
"""
from __future__ import annotations
import argparse
import csv
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys
import subprocess
import unicodedata

import joblib
import sklearn
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from ml.train import ROOT, MODEL_DIR, load_rows
from ml.training_seed import ASPECTS, SENTIMENTS, all_examples
from ml.candidate_features import candidate_pipeline

ASPECT_MAP = {code.replace("_", " ").lower(): code for code in ASPECTS}
PROBES = [
    ("ung mga PC hindi nagagamit and sira ung ibang parts kaya hindi nagagamit lalo na kapag kailangan.", "negative", "facility_conditions"),
    ("Hindi sira ang mga computer.", "positive", "facility_conditions"),
    ("Hindi mabilis ang pag release ng documents.", "negative", "processing_time"),
    ("ang bilis magpahintay ng mga tao nakakainip", "negative", "processing_time"),
    ("sira ang mouse, sana palitan", "constructive", "facility_conditions"),
    ("Continue providing efficient and friendly service.", "positive", "staff_responsiveness"),
    ("I hope they will continue ensuring comfort and safety.", "positive", "facility_conditions"),
    ("Ang mahal ng pagkain.", "negative", ""),
]


def key(text):
    import re
    text = unicodedata.normalize("NFKC", text).casefold().replace("?", "'")
    return " ".join(re.findall(r"\w+", text))


def similar(a, b):
    return a == b or (min(len(a), len(b)) >= 25 and SequenceMatcher(None, a, b).ratio() >= .9)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        sample = stream.read(4096)
        stream.seek(0)
        return list(csv.DictReader(stream, delimiter="\t" if "\t" in sample.splitlines()[0] else ","))


def normalized(row, origin, index):
    aspect = (row.get("aspect_code", row.get("aspect", "")) or "").strip()
    aspect = ASPECT_MAP.get(aspect.replace("_", " ").lower(), aspect)
    sentiment = (row.get("sentiment") or "").strip().lower()
    issues = []
    if not (row.get("text") or "").strip(): issues.append("empty text")
    if sentiment not in SENTIMENTS: issues.append("excluded/unknown sentiment")
    if aspect and aspect not in ASPECTS: issues.append("unknown aspect")
    if row.get("include_in_training", "Yes").casefold() != "yes": issues.append("explicit exclusion")
    if "\ufffd" in row.get("text", ""): issues.append("encoding replacement character: recover original text")
    return dict(id=row.get("id") or f"{origin}-{index}", text=row.get("text", ""),
                sentiment=sentiment, aspect_code=aspect, language=row.get("language", ""),
                source=row.get("source") or origin, respondent=row.get("respondent", ""),
                service_area=row.get("service_area", ""), review_note=row.get("review_note", ""),
                origin=origin, issues="; ".join(issues), approved="no", split="",
                genuine_independent="no", baseline_group_unseen="unknown")


def groups(rows):
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(i,j):
        parent[find(i)] = find(j)
    keys = [key(r["text"]) for r in rows]
    for i, row in enumerate(rows):
        for j in range(i):
            other = rows[j]
            # Source is intentionally conservative: one survey batch stays together.
            shared_source = row["source"] and row["source"] == other["source"]
            shared_person = row.get("respondent") and row["respondent"] == other.get("respondent") and row["source"] == other["source"]
            if shared_source or shared_person or similar(keys[i], keys[j]): union(i,j)
    return [find(i) for i in range(len(rows))]


def metrics(model, rows, target):
    labels = list(SENTIMENTS if target == "sentiment" else ASPECTS)
    use = [r for r in rows if r[target]]
    if not use: return {"n": 0, "not_evaluable": True}
    truth = [r[target] for r in use]
    pred = [str(p) for p in model.predict([r["text"] for r in use])]
    return dict(n=len(use), distribution=dict(Counter(truth)), labels=labels,
                macro_f1=f1_score(truth,pred,labels=labels,average="macro",zero_division=0),
                per_class=classification_report(truth,pred,labels=labels,output_dict=True,zero_division=0),
                confusion_matrix=confusion_matrix(truth,pred,labels=labels).tolist(),
                misclassifications=[dict(id=r["id"],text=r["text"],truth=t,predicted=p)
                                    for r,t,p in zip(use,truth,pred) if t!=p][:20])


def snapshot(out):
    out.mkdir(parents=True, exist_ok=False)
    backup = out/"baseline"
    backup.mkdir()
    hashes = {}
    for name in ("sentiment_nb.joblib", "aspect_nb.joblib"):
        shutil.copy2(MODEL_DIR/name, backup/name)
        hashes[name] = digest(MODEL_DIR/name)
    shutil.copytree(ROOT/"ml", out/"code", ignore=shutil.ignore_patterns("models", "__pycache__"))
    shutil.copy2(ROOT/"data"/"training_comments.csv", out/"legacy_training_comments.csv")
    result = subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True)
    environment = subprocess.run([sys.executable,"-m","pip","freeze"],capture_output=True,text=True,check=True)
    (out/"requirements-frozen.txt").write_text(environment.stdout,encoding="utf-8")
    metadata = dict(model_sha256=hashes, git_commit=result.stdout.strip(), python=platform.python_version(),
                    sklearn=sklearn.__version__, source_hashes={p.name:digest(p) for p in (ROOT/"ml").glob("*.py")})
    (out/"baseline.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    return hashes


def audit(inputs, out):
    hashes = snapshot(out)
    records = [normalized(row, str(Path(path).resolve()), i+1) for path in inputs for i,row in enumerate(read_csv(path))]
    legacy = defaultdict(list)
    # Keep seed and CSV evidence separately: never silently resolve conflicts.
    for origin, rows in (("seed", all_examples()), ("legacy_csv", [(r["text"],r["aspect_code"],r["sentiment"],r["language"]) for r in read_csv(ROOT/"data"/"training_comments.csv")])):
        for text,aspect,sentiment,_ in rows:
            legacy[key(text)].append(dict(origin=origin,sentiment=sentiment,aspect_code=aspect))
    collisions=[]; near=[]; duplicate=[]; seen={}
    for i,r in enumerate(records):
        k=key(r["text"])
        if k in seen: duplicate.append(dict(id=r["id"],same_as=records[seen[k]]["id"],label_conflict=any(r[t]!=records[seen[k]][t] for t in ("sentiment","aspect_code"))))
        else: seen[k]=i
        if k in legacy: collisions.append(dict(id=r["id"],proposed={t:r[t] for t in ("sentiment","aspect_code")},existing=legacy[k]))
        for lk in legacy:
            if k!=lk and similar(k,lk): near.append(dict(id=r["id"],legacy_text_key=lk))
    ids=groups(records)
    for r,g in zip(records,ids): r["group"]=f"group-{g:04d}"
    with (out/"review.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    # Baseline is diagnostic on provisional, deduplicated annotations, NOT a holdout score.
    unique=[]
    for i,r in enumerate(records):
        if not r["issues"] and seen[key(r["text"]) ]==i: unique.append(r)
    models={t:joblib.load(out/"baseline"/f"{t}_nb.joblib") for t in ("sentiment","aspect")}
    report=dict(schema="text,aspect_code,sentiment,language",provisional=True,independent_test=False,
                input_sha256={str(Path(p).resolve()):digest(p) for p in inputs},
                raw_rows=len(records),unique_texts=len(seen),sentiments=dict(Counter(r["sentiment"] for r in unique)),
                aspects=dict(Counter(r["aspect_code"] for r in unique)),groups=dict(Counter(r["group"] for r in records)),
                issues=[{ "id":r["id"],"issues":r["issues"]} for r in records if r["issues"]],
                duplicates=duplicate,legacy_overlaps=collisions,near_legacy_matches=near,
                baseline={t:metrics(m,unique,"sentiment" if t=="sentiment" else "aspect_code") for t,m in models.items()})
    (out/"audit.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    assert hashes=={n:digest(MODEL_DIR/n) for n in hashes}
    print(f"Staged {len(records)} provisional rows, {len(seen)} unique texts. No legacy data/models changed. Review {out/'audit.json'}.")


def validate_experiment(rows):
    for r in rows:
        if r.get("approved")!="yes" or r.get("issues"): raise ValueError("Every experiment row must be explicitly approved with issues resolved")
        if r.get("split") not in {"train","validation","holdout"}: raise ValueError("Assign train/validation/holdout BEFORE evaluation")
        if r["sentiment"] not in SENTIMENTS or (r["aspect_code"] and r["aspect_code"] not in ASPECTS): raise ValueError("Invalid label")
    families=groups(rows)
    for family in set(families):
        if len({r["split"] for r,g in zip(rows,families) if g==family})!=1: raise ValueError("Source/respondent/near-duplicate family crosses splits")
    keys=[key(r["text"]) for r in rows]
    if len(set(keys))!=len(keys): raise ValueError("Resolve duplicate texts explicitly; do not weight repeats")
    legacy=[key(r[0]) for r in load_rows()]
    for r in rows:
        if r["split"] in {"validation","holdout"}:
            if r.get("genuine_independent")!="yes" or r.get("baseline_group_unseen")!="yes": raise ValueError("Evaluation requires genuine independent data and verified unseen baseline groups")
            if any(similar(key(r["text"]),k) for k in legacy): raise ValueError("Evaluation text overlaps baseline training corpus")
    for split in ("train","validation","holdout"):
        subset=[r for r in rows if r["split"]==split]
        for target,labels in (("sentiment",SENTIMENTS),("aspect_code",ASPECTS)):
            counts=Counter(r[target] for r in subset if r[target])
            minimum=3 if split=="train" else 1
            if any(counts[label]<minimum for label in labels): raise ValueError(f"Insufficient {target} coverage in {split}: {dict(counts)}")


def experiment(review, out):
    rows=read_csv(review)
    validate_experiment(rows)  # fail BEFORE fitting/writing candidate artifacts
    hashes=snapshot(out)
    shutil.copy2(review,out/"frozen_review.csv")
    report={"policy":"Fixed paper families: SVM sentiment, ComplementNB aspect; no holdout-driven selection", "manifest_sha256":digest(review)}
    train=[r for r in rows if r["split"]=="train"]
    for task,choice,target in (("sentiment","svm","sentiment"),("aspect","cnb","aspect_code")):
        use=[r for r in train if r[target]]
        candidate=candidate_pipeline(choice).fit([r["text"] for r in use],[r[target] for r in use])
        joblib.dump(candidate,out/f"candidate_{task}.joblib")
        baseline=joblib.load(out/"baseline"/f"{task}_nb.joblib")
        report[task]={}
        for split in ("validation","holdout"):
            subset=[r for r in rows if r["split"]==split]
            report[task][split]={name:metrics(m,subset,target) for name,m in (("baseline",baseline),("candidate",candidate))}
        probes=[dict(id=f"probe-{i}",text=t,sentiment=s,aspect_code=a) for i,(t,s,a) in enumerate(PROBES)]
        report[task]["exploratory_probes"]={name:metrics(m,probes,target) for name,m in (("baseline",baseline),("candidate",candidate))}
    (out/"comparison.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    assert hashes=={n:digest(MODEL_DIR/n) for n in hashes}
    print(f"Comparison saved to {out}; no automatic promotion. Holdout is now consumed: do not tune on these results.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="action",required=True)
    p=sub.add_parser("audit");p.add_argument("inputs",nargs="+");p.add_argument("--out",type=Path,required=True)
    p=sub.add_parser("experiment");p.add_argument("review");p.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.action=="audit": audit(args.inputs,args.out)
        else: experiment(args.review,args.out)
    except ValueError as exc: parser.exit(2,f"Refused: {exc}\n")

if __name__=="__main__": main()
