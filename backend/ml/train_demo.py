"""Build the demo classifiers using invented text only."""

import joblib

from ml.aspect_taxonomy import ASPECT_CODES, taxonomy_document
from ml.aspect_transition import indicator
from ml.features import build_pipeline
from ml.multilabel_aspects import balanced_aspect_pipeline
from ml.polarity_v4 import fingerprint
from ml.train import MODEL_DIR
from ml.train_polarity_v4 import build as build_polarity
from ml.training_seed import all_examples


NEUTRAL = (
    "I submitted a request at the office.",
    "My class was scheduled for the morning.",
    "The library has a desk near the entrance.",
    "May form sa tabi ng pinto.",
    "Nasa ikalawang palapag ang opisina.",
    "Nagpunta ako sa klinika noong Martes.",
    "I printed the form bago pumunta sa office.",
    "Sa website ko nakita ang contact number.",
    "May orientation sa room next week.",
    "I sent an email to ask about the schedule.",
    "The sign lists the opening hours.",
    "Dumaan ako sa canteen bago ang klase.",
)

EXTRA_ASPECTS = {
    "digital_services": (
        "The campus Wi-Fi disconnects every few minutes.",
        "Hindi naglo-load ang online portal.",
        "Please make the website work on mobile.",
    ),
    "affordability_value": (
        "The meal price is too high for my budget.",
        "Mahal ang bayad sa pag-print.",
        "Please offer a cheaper lunch option.",
    ),
    "service_program_quality": (
        "The orientation workshop explained enrollment clearly.",
        "Sariwa at masarap ang pagkain sa kantina.",
        "The tutoring program needs more practice exercises.",
    ),
    "fairness_inclusion_policy": (
        "The rule was applied differently to students in the same situation.",
        "Hindi pantay ang pagtrato sa dalawang grupo.",
        "Please use the same grading criteria for everyone.",
    ),
}


def main():
    rows = list(all_examples())
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    texts, aspects, sentiments, _ = zip(*rows)
    legacy_sentiment = build_pipeline("cnb").fit(texts, sentiments)
    legacy_aspect = [(text, aspect) for text, aspect in zip(texts, aspects) if aspect]
    legacy_texts, legacy_codes = zip(*legacy_aspect)
    joblib.dump(legacy_sentiment, MODEL_DIR / "sentiment_nb.joblib")
    joblib.dump(build_pipeline("cnb").fit(legacy_texts, legacy_codes), MODEL_DIR / "aspect_nb.joblib")

    polarity_rows = [(text, label) for text, label in zip(texts, sentiments) if label != "constructive"]
    polarity_rows.extend((text, "neutral") for text in NEUTRAL)
    polarity_texts, polarity_labels = zip(*polarity_rows)
    polarity = build_polarity().fit(polarity_texts, polarity_labels)
    joblib.dump(
        {"version": "polarity-v4", "fingerprint": fingerprint(), "model": polarity},
        MODEL_DIR / "polarity_v4.joblib",
    )

    aspect_rows = [{"text": text, "aspect_codes": [code]} for text, code in legacy_aspect]
    aspect_rows.extend(
        {"text": text, "aspect_codes": [code]}
        for code, examples in EXTRA_ASPECTS.items()
        for text in examples
    )
    aspect_model = balanced_aspect_pipeline().fit([row["text"] for row in aspect_rows], indicator(aspect_rows))
    joblib.dump(
        {
            "version": "demo-aspects-v2",
            "taxonomy": taxonomy_document(),
            "aspect_codes": ASPECT_CODES,
            "pipeline": aspect_model,
            "threshold": 0.5,
            "thresholds": [0.5] * len(ASPECT_CODES),
        },
        MODEL_DIR / "aspect_v2.joblib",
    )


if __name__ == "__main__":
    main()
