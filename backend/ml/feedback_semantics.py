"""Versioned interpretation rules; original comment text is never modified.

Rules use the complaint/request, not a person's gender or identity. They are
explicit decision aids, not a claim that all sarcasm can be understood.
"""
import re
from ml.features import normalize_text, POS_WORDS, NEG_WORDS, NEGATION_WORDS, _polarity

POLICY_VERSION = "sentiment-policy-v3"
from ml.aspect_taxonomy import GENERAL_ASPECT
GENERAL_ASPECT_CODE = GENERAL_ASPECT.code
GENERAL_ASPECT_NAME = GENERAL_ASPECT.name

GENERAL_POSITIVE = {
    "good", "great", "okay", "ok", "nice", "excellent", "functional", "fine",
    "very good", "very nice", "good service", "excellent service", "very great",
    "good enough", "just good", "good naman", "goods", "goods naman", "okay naman",
    "all good", "well done", "ayos", "maayos", "no issues", "no problem", "no complaints",
}
GENERAL_NEGATIVE = {
    "bad", "poor", "very bad", "very poor", "not good", "not okay", "not ok",
    "not nice", "not great", "terrible", "disappointing", "not satisfied",
}
GENERAL_CONSTRUCTIVE = {"improve it", "improve service", "need improvement", "needs improvement",
                        "need improvements", "need more improvement", "need more improvements"}
AMBIGUOUS_FRAGMENTS = {"sakto lang mej lang", "mej lang naman", "not all the times"}
NON_EVALUATIONS = {
    "none", "na", "n a", "no comment", "no comments", "not applicable", "nothing",
    "nothing to add", "non", "tt", "no", "no e", "noe", "i dont know", "i do not know",
    "wala ako explanation", "wala akong masabi", "hindi ko alam", "di ko alam",
    "so far ive only been there for few specific reason", "ang hirap mo e explain",
    "i want to keep it confidential", "hello", "thanks", "thank you", "thank you po", "thanks po",
}


def general_sentiment(text):
    normalized = normalize_text(text)
    if normalized in GENERAL_POSITIVE:
        return "positive"
    if normalized in GENERAL_NEGATIVE:
        return "negative"
    if normalized in GENERAL_CONSTRUCTIVE:
        return "constructive"
    if re.fullmatch(r"(?:very |so |really |just )?(?:good|great|okay|ok|nice|excellent|fine|goods)(?: service)?(?: po| naman| lang){0,2}", normalized):
        return "positive"
    return None


def is_general_feedback(text):
    return bool(general_sentiment(text)) or normalize_text(text) in AMBIGUOUS_FRAGMENTS


def unsupported_feedback(text):
    from app.services.feedback_text import is_no_substantive_feedback
    normalized = normalize_text(text)
    if general_sentiment(text):
        return False  # OK is a valid short evaluation; NA is not.
    identity_only = re.fullmatch(r"(?:the )?(?:guard|guards|staff|personnel|personel) (?:is|are) (?:a )?(?:female|male|woman|man|tomboy|lgbtq?|babae|lalaki)", normalized)
    return (not re.search(r"[a-z]", normalized) or len((text or "").strip()) < 3 or is_no_substantive_feedback(text)
            or normalized in NON_EVALUATIONS
            or bool(identity_only)
            or bool(re.fullmatch(r"(?:i (?:don ?t|do not) eat in (?:the )?canteen|i have no experience(?: with (?:this|the) service)?|ive never been to any offices.*(?:dont|do not) (?:really )?know (?:their|the) system)", normalized)))


NEGATIVE_EXTRA = {
    "ignoring", "unreasonable", "moody", "scary", "unrespect", "disrespect", "disrespectful",
    "worst", "bad", "intimidating", "unfair", "unavailable", "unusable", "smelly",
    "insufficient", "expensive", "overpriced", "pricey", "mahal", "disappointed",
    "disappointing", "inconsistent", "unequal", "sungit", "masusungit", "mataray", "matataray", "maldita",
    "nasisigawan", "sinisigawan", "sumisigaw", "shouting", "yelling", "sirang", "mahina", "reklamo",
}
POSITIVE_EXTRA = {"fair", "responsive", "understanding", "usable", "working", "work", "works", "nagagamit", "magamit",
                  "active", "available", "reliable", "ventilated", "maintained", "appreciated", "caring", "attentive",
                  "sarap", "masarap", "delicious", "tasty", "busog", "support", "supportive", "progressive", "respectful"}
NEGATORS = NEGATION_WORDS | {"none", "arent", "werent", "hasnt", "havent"}
CLAUSES = re.compile(r"[.;!?,]+|\b(?:and|but|pero|at|kaya|though|although|however)\b", re.I)
NEGATIVE_PHRASES = (
    r"\b(?:hard|difficult) to (?:reach|contact)\b",
    r"\b(?:may|has|have|with) (?:an? |bad |po )*attitude\b",
    r"\bakala mo\b.{0,30}\b(?:tagapagmana|taga pag ?mana|may ari)\b",
    r"\bbilis\b.{0,35}\b(?:magpahintay|paghihintay)\b",
    r"\b(?:no|without|walang|wala) (?:running |hot |cold |clean |supply of )?(?:water|tubig|staff|tao|service|services)\b",
    r"\b(?:not|no) enough\b",
    r"\b(?:walang|wala) (?:consideration|aksyon|aksuyon)\b",
    r"\b(?:lack(?:s)?(?: of)?|without) (?:proper )?(?:ventilation|equipment|water|materials)\b",
    r"\b(?:cant|cannot|can t) say the same\b",
    r"\b(?:employees|staff|personnel) (?:are )?playing games\b",
)
NEGATIVE_PHRASE_RE = re.compile("|".join(NEGATIVE_PHRASES))


def _negated(tokens, index, polarity=0):
    count = 0
    fillers={"a","an","the","any","of","these","our","their","are","is","mga","na","naman","very","really",
             "staff","people","personnel","computers","computer","pc","pcs","fan","fans","equipment","service","services"}
    for j in range(max(0, index - 12), index):
        partial = tokens[j] == "not" and j+1 < len(tokens) and tokens[j+1] in ("all","always")
        if partial:
            count += polarity > 0
            continue
        if j < index-5 and not (polarity > 0 and tokens[j] == "not" and tokens[j+1:j+2] == ["people"]): continue
        if tokens[j] in {"no","without","wala","walang","none"} and any(t not in fillers for t in tokens[j+1:index]):
            continue  # absence of one noun does not negate a later complaint
        if tokens[j] in NEGATORS and not (tokens[j] == "not" and j+1 < len(tokens) and tokens[j+1] in ("only", "just", "unless")):
            count += 1
    return count % 2 == 1


def sentiment_evidence(text):
    positive, negative = [], []
    for clause in CLAUSES.split(str(text)):
        normalized = normalize_text(clause)
        tokens = normalized.split()
        for i, token in enumerate(tokens):
            polarity = -1 if token in NEGATIVE_EXTRA else 1 if token in POSITIVE_EXTRA else _polarity(token)
            if token == "kind" and i > 0 and tokens[i-1] == "some" and i+1 < len(tokens) and tokens[i+1] == "of":
                polarity = 0  # "some kind of proof" is not praise for staff.
            if token in {"work", "works", "working"} and not any(t in {"computer", "computers", "pc", "pcs", "fan", "fans", "equipment", "system", "systems", "internet", "wifi", "aircon"} for t in tokens[max(0,i-6):i]):
                polarity = 0
            if polarity and _negated(tokens, i, polarity):
                polarity = -polarity
            if polarity > 0:
                positive.append(token)
            elif polarity < 0:
                negative.append(token)
        for match in NEGATIVE_PHRASE_RE.finditer(normalized):
            before = normalized[:match.start()].split()
            (positive if _negated(before + ["target"], len(before), -1) else negative).append(match.group())
    return {"positive": positive, "negative": negative}


def improvement_request(text):
    norm = normalize_text(text)
    continuation = bool(re.search(r"\b(?:continue|continuing|keep|maintain)\b", norm))
    change = re.search(r"\b(?:improv\w*|upgrad\w*|fix\w*|repair\w*|add|replace|better|palitan|dagdagan|magdagdag|ayusin|linisin|maglagay|palawigin|paki\w+)\b", norm)
    direct_request = re.search(r"\b(?:sana|dapat|should|shouldnt|suggest\w*|suhest\w*|mungkahi)\b", norm)
    if continuation and not change and not direct_request:
        return bool(re.search(r"^maintain (?:cleanliness|sanitation|water)\b", norm))
    explicit = bool(re.search(r"\b(?:sana|dapat|should|shouldnt|suggest\w*|suhest\w*|mungkahi)\b", norm)
        or re.search(r"\bhow (?:can|could) (?:we|they|you) improv\w*\b", norm)
        or re.search(r"\b(?:hope|wish|hopefully)\b.{0,160}\b(?:more|better|improv\w*|upgrad\w*|can|could|will|allowed|available|stable|clean|responsive|fair|respectful|mapalitan|madagdagan|maayos)\b", norm))
    if explicit:
        return True
    return bool(
        re.search(r"\b(?:sana|dapat|should|shouldnt|suggest\w*|suhest\w*|mungkahi)\b", norm)
        or re.search(r"\b(?:hope|wish|hopefully)\b.{0,100}\b(?:more|better|improv\w*|upgrad\w*|can|will|available|stable|clean|responsive|fair|respectful)\b", norm)
        or re.search(r"\b(?:please|pls|recommend\w*|consider\w*)\b", norm) and change
        or re.search(r"\b(?:need|needs|needed)\b.{0,25}\b(?:more|improv\w*|upgrad\w*|repair\w*|fix\w*|water|tabo)\b", norm)
        or re.search(r"^be (?:more |less )?(?:available|responsive|understanding|approachable|open|respectful|fair)\b", norm)
        or re.search(r"^(?:improv\w*|add|replace|fix|palitan|dagdagan|ayusin|linisin|paki\w*)\b", norm)
        or re.search(r"\bmas (?:okay|ok|mabuti|mainam|maganda)\b", norm) and bool(sentiment_evidence(text)["negative"])
        or re.search(r"\b(?:wag|huwag)\b.{0,30}\b(?:galit|masungit|sigaw)\b", norm))


def policy_decision(text):
    if unsupported_feedback(text):
        return {"label": None, "reason": "unsupported_or_no_evaluation", "evidence": []}
    if normalize_text(text) in AMBIGUOUS_FRAGMENTS:
        return {"label": None, "reason": "ambiguous_general_feedback", "evidence": []}
    general = general_sentiment(text)
    if general:
        return {"label": general, "reason": "general_evaluation", "evidence": [normalize_text(text)]}
    evidence = sentiment_evidence(text)
    if improvement_request(text):
        return {"label": "constructive", "reason": "explicit_improvement_request", "evidence": evidence["negative"]}
    if evidence["negative"]:
        return {"label": "negative", "reason": "complaint_takes_priority", "evidence": evidence["negative"]}
    if evidence["positive"] and any(t in normalize_text(text).split() for t in NEGATORS) and not re.search(r"\bnot (?:always|all)\b", normalize_text(text)):
        return {"label": "positive", "reason": "negated_complaint_without_other_negative_evidence", "evidence": evidence["positive"]}
    if re.search(r"\b(?:continue|continuing|maintain|keep)\b", normalize_text(text)) and not evidence["negative"]:
        return {"label": "positive", "reason": "continue_existing_positive_service", "evidence": evidence["positive"]}
    return {"label": None, "reason": "learned_model_required", "evidence": []}
