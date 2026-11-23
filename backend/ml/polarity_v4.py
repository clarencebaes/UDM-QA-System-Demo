"""Three learned polarities; suggestion type and language are independent.

Never infer a comment's sentiment from its star rating. Questions supply topic
context only, except explicit yes/no answers to the positive survey statements.
"""
import re
import hashlib
from pathlib import Path
import joblib
from ml.features import normalize_text
from ml.feedback_semantics import sentiment_evidence, improvement_request, general_sentiment
from app.services.feedback_text import is_no_substantive_feedback

VERSION = "polarity-language-v4.1"
ARTIFACT = Path(__file__).parent / "models" / "polarity_v4.joblib"
_bundle = None

def fingerprint():
    root=Path(__file__).parent
    return hashlib.sha256(b"".join((root/name).read_bytes().replace(b"\r\n",b"\n") for name in ("polarity_v4.py","train_polarity_v4.py","features.py","feedback_semantics.py"))).hexdigest()
TYPO = {"critizing":"criticizing", "critisizing":"criticizing", "securty":"security", "unifrms":"uniforms", "serbisy":"serbisyo", "mabagel":"mabagal", "mabgal":"mabagal", "mabaitt":"mabait"}
TL = set("ang ng mga sa ay at po opo oo hindi wala walang naman lang sana dapat pero kasi kapag kung bakit paano ako akong ko kami namin natin sila nila siya ito itong dito doon din rin na nang ni may mas lahat para pa ba paki maayos mabait mabagal mabilis malinis marumi sira tubig palagi ngayon pumunta kumuha nagpunta ginamit nagagamit napunta nakapunta kumain nagtanong hinintay naghintay opisina silid paaralan aklatan silidaklatan guro magaaral pagkain presyo mahal maganda masarap serbisyo tulong mabuti mahinahon minsan buong araw oras palikuran pasilidad sinasabi sinabi nagbigay nagdala dokumento nakalagay tuwing bawat pagkatapos palang nangyari sumagot kinuha kinakailangan pinuntahan inabot dalawang beses tuwing".split())
EN = set("the a an is are was were am i we they it my our their your you me and but or because when if on in at to of for with from this that these those have has had only been there went used use submitted collected asked requested visited attended bought ate signed filled took received during after before twice once today yesterday class room classroom service staff security office library computer laboratory canteen clinic campus facilities water document documents request form hours time queue uniforms uniform students student need needs should please improve clean slow dirty broken fair respectfully respectful helpful available good bad excellent friendly rude working wifi online processing course courses school tuition permit released assistance equipment ventilation light lights printed books book desks chairs".split())
EN.update("yes no ok okay agree disagree nice great fine awesome terrible outstanding decent thanks thank never not all any so far specific reasons reading read open closed lighting comfortable sufficient respect polite courteous quality price noisy busy hot cold safe unsafe maintained".split())
TL.update("salamat matulungin salamat bukas sarado mainit malamig tahimik magalang patas sapat tagal bilis ganda sirang nakakuha nakatanggap nakatulong nakapag nakapagbigay nakita pumila mababait maingay maluwag maaliwalas".split())

def normalized(text):
    return " ".join(TYPO.get(word,word) for word in normalize_text(text).split())

def detect_language(text):
    if is_no_substantive_feedback(text) or not (text or "").strip(): return "undetermined"
    tokens=normalized(text).split()
    tl={t for t in tokens if t in TL and t not in {"at","may"}}
    en={t for t in tokens if t in EN and t not in TL}
    # Proper names and unknown words alone are not evidence of English.
    if tl and en: return "taglish"
    if tl: return "tagalog"
    if en: return "english"
    return "undetermined"

def load(force=False):
    global _bundle
    if force or _bundle is None:
        _bundle=joblib.load(ARTIFACT)
        if set(_bundle["model"].classes_)!={"positive","negative","neutral"}: raise ValueError("Invalid v4 polarity classes")
        if _bundle.get("fingerprint")!=fingerprint(): raise ValueError("Rebuild the polarity artifact after changing analysis code")
    return _bundle

def analyze(text, questions=()):
    norm=normalized(text)
    language=detect_language(text)
    result=dict(label=None,polarity=None,is_constructive=False,language=language,model_probability=0.0,reason="no_substantive_text",version=VERSION)
    if not norm or is_no_substantive_feedback(text): return result
    if not re.search(r"[a-z]",norm) or (language=="undetermined" and len(norm.split())<3 and norm not in {"yes","no","ok","okay","good","bad","agree","disagree"}):
        return {**result,"reason":"insufficient_language_evidence"}
    suggestion=bool(improvement_request(norm))
    evidence=sentiment_evidence(norm)
    # Common typo variants are corrected only against the small cue vocabulary.
    extra_neg=bool(re.search(r"\b(?:criticiz\w*|critisiz\w*|unrespect\w*|overstrict|too strict|too much|sobrang higpit|hindi patas|namamahiya|naninigaw)\b",norm))
    # The supplied uniform-enforcement example is an author-confirmed implicit
    # improvement request; its dissatisfaction remains Negative polarity.
    suggestion=suggestion or bool(re.search(r"\bcriticiz\w*\b.*\buniforms?\b",norm))
    general=general_sentiment(norm)
    factual_nonuse=bool(re.search(r"\b(?:have not used|never used|no experience|hindi ko pa (?:na ?try|nagagamit|nasubukan)|hindi pa (?:nagagamit|nasubukan))\b",norm))
    factual_identity=bool(re.fullmatch(r"(?:the )?(?:guard|guards|staff|personnel) (?:is|are) (?:a )?(?:female|male|woman|man|babae|lalaki)|(?:babae|lalaki) ang (?:guard|staff|tauhan)",norm))
    if factual_identity: polarity="neutral";reason="factual_description"
    elif factual_nonuse and not extra_neg and not suggestion: polarity="neutral";reason="factual_nonuse"
    elif questions and norm in {"yes","yes po","oo","opo","agree","sang ayon"}: polarity="positive";reason="affirmed_survey_statement"
    elif questions and norm in {"no","hindi","hindi po","disagree"}: polarity="negative";reason="disagreed_survey_statement"
    elif extra_neg or evidence["negative"]: polarity="negative";reason="negative_text_evidence"
    elif general in {"positive","negative"}: polarity=general;reason="explicit_evaluation"
    elif evidence["positive"]: polarity="positive";reason="positive_text_evidence"
    elif suggestion: polarity="neutral";reason="suggestion_without_expressed_valence"
    else:
        model=load()["model"]
        probabilities=model.predict_proba([norm])[0]
        index=int(probabilities.argmax());polarity=str(model.classes_[index]);reason="learned_polarity"
        if max(probabilities)<.40:
            return {**result,"is_constructive":suggestion,"reason":"uncertain_polarity"}
    model=load()["model"]
    probabilities=model.predict_proba([norm])[0]
    confidence=float(probabilities[list(model.classes_).index(polarity)])
    return {**result,"label":"constructive" if suggestion else polarity,"polarity":polarity,"is_constructive":suggestion,"model_probability":confidence,"reason":reason}
