"""Train a separate three-class NB artifact; never overwrite aspect/v3 models.

Neutral examples are authored domain fixtures, not collected student responses.
Constructive labels in the old corpus are not silently relabeled Neutral.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import joblib
import sklearn
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import ComplementNB
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.metrics import classification_report
from ml.features import normalize_text
from ml.train import load_rows, MODEL_DIR
from ml.aspect_transition import families
from ml.polarity_v4 import fingerprint, VERSION

def build():
    return Pipeline([("features",FeatureUnion([
        ("word",TfidfVectorizer(preprocessor=normalize_text,ngram_range=(1,2),sublinear_tf=True)),
        ("char",TfidfVectorizer(preprocessor=normalize_text,analyzer="char_wb",ngram_range=(2,5),sublinear_tf=True))])),
        ("classifier",ComplementNB(alpha=.5))])

def train():
    rows={normalize_text(t):dict(text=t,label=s,source="existing-domain-corpus") for t,a,s,l in load_rows() if s in {"positive","negative"}}
    source=Path(__file__).resolve().parents[1]/"data"/"neutral_v4.csv"
    for row in csv.DictReader(source.open(encoding="utf-8")):
        key=normalize_text(row["text"])
        if key in rows and rows[key]["label"]!="neutral": raise ValueError("Conflicting authored neutral example")
        rows[key]=dict(text=row["text"],label="neutral",source="authored-neutral-fixture")
    rows=list(rows.values());X=[r["text"] for r in rows];y=[r["label"] for r in rows]
    groups=families([{"text":r["text"]} for r in rows])
    folds=list(StratifiedGroupKFold(n_splits=3,shuffle=True,random_state=42).split(X,y,groups))
    predictions=cross_val_predict(build(),X,y,cv=folds)
    report={"version":"polarity-v4","training_rows":len(rows),"classes":dict(Counter(y)),
        "policy_version":VERSION,"sklearn_version":sklearn.__version__,"analysis_code_sha256":fingerprint(),
        "training_corpus_sha256":hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        "grouped_cross_validation":classification_report(y,predictions,output_dict=True,zero_division=0),
        "neutral_source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "limitations":"Small domain corpus and authored neutral examples. Grouped development cross-validation is not independently annotated live-student accuracy. No private comments were sent to external services. Constructive detection is a separate rule-based feedback type."}
    model=build().fit(X,y)
    joblib.dump({"version":"polarity-v4","fingerprint":fingerprint(),"model":model,"evaluation":report},MODEL_DIR/"polarity_v4.joblib")
    out=Path(__file__).resolve().parents[2]/"docs"/"polarity-v4-evaluation.json"
    out.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":train()
