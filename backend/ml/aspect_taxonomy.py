"""Nine learned aspects plus a separate general-feedback routing category."""
from dataclasses import asdict, dataclass

TAXONOMY_VERSION = "quad-aspects-v2-draft-1"


@dataclass(frozen=True)
class AspectDefinition:
    code: str
    name: str
    includes: str
    boundary: str


DEFINITIONS = (
    AspectDefinition("processing_time", "Processing Time",
        "Queues, waiting, repeated processing visits, document turnaround and release delays.",
        "An unavailable or closed office is accessibility unless a processing delay is also stated."),
    AspectDefinition("staff_responsiveness", "Staff Support and Professionalism",
        "Helpfulness, attentiveness, responsiveness, approachability, respectful or rude interactions.",
        "Use fairness for explicit unequal treatment or policy enforcement; tag both only if both are expressed."),
    AspectDefinition("communication_clarity", "Communication Clarity",
        "Unclear, missing or contradictory announcements, requirements, instructions and service information.",
        "A disliked announcement is not necessarily unclear. Website performance belongs to digital services."),
    AspectDefinition("service_accessibility", "Service Availability and Accessibility",
        "Opening hours, closures, appointments, contact channels, access restrictions and available services.",
        "Physical defects alone belong to facilities. Also tag accessibility when closure or restricted access is explicit."),
    AspectDefinition("facility_conditions", "Physical Facilities and Equipment",
        "Restroom cleanliness, sanitation, water, ventilation, lighting, rooms, furniture and physical equipment.",
        "Wi-Fi and website faults belong to digital services; prepared food quality belongs to service/program quality."),
    AspectDefinition("digital_services", "Digital Services and Connectivity",
        "Wi-Fi, internet speed, digital platform reliability, website functionality and interface usability.",
        "Broken computer hardware belongs to facilities; unclear information on a working website belongs to communication."),
    AspectDefinition("affordability_value", "Affordability and Value",
        "Prices, costs, affordability and explicitly stated value for money.",
        "Do not infer this from food mentions. Food taste or quality without a cost claim belongs to service/program quality."),
    AspectDefinition("service_program_quality", "Service and Program Quality",
        "Quality, usefulness or adequacy of teaching, learning resources, healthcare, food, activities and programs.",
        "Identify the service using its recorded service area. Do not infer a topic from generic praise such as Good."),
    AspectDefinition("fairness_inclusion_policy", "Fairness, Inclusion and Policy Implementation",
        "Unequal treatment, inclusion, discrimination, grading fairness and inconsistent or challenged policy enforcement.",
        "Rudeness alone is staff professionalism. Do not infer discrimination or validate an allegation from the label."),
)
ASPECT_CODES = tuple(item.code for item in DEFINITIONS)
LEGACY_CODES = ASPECT_CODES[:5]
GENERAL_ASPECT = AspectDefinition("general_service_feedback", "General Service Feedback",
    "A meaningful overall evaluation without a specific topic, such as Good, Great, Okay, Bad or Improve it.",
    "Not a substitute for a supported specific topic. Placeholders and non-evaluations remain N/A.")
CATALOG_DEFINITIONS = DEFINITIONS + (GENERAL_ASPECT,)


def taxonomy_document():
    return {"version": TAXONOMY_VERSION, "status": "proposed-not-production",
            "annotation_unit": "One original comment; zero, one or multiple supported aspects",
            "definitions": [asdict(item) for item in DEFINITIONS]}
