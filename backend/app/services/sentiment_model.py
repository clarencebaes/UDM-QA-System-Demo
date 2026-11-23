"""Three-class polarity model with separate suggestion and language analysis."""
from ml.polarity_v4 import analyze, load, VERSION

def load_sentiment_model():
    load(force=True)

def predict_sentiment(text, fallback_model=None, questions=()):
    return analyze(text, questions)

def sentiment_status():
    return {"sentiment_model_version":"polarity-v4", "sentiment_policy_version":VERSION,
            "sentiment_classes":["positive","negative","neutral"],
            "feedback_types":["constructive"], "language_classes":["english","tagalog","taglish","undetermined"]}
