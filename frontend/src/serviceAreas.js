export const SERVICE_AREAS = [
  {
    code: "deans_office",
    name: "Dean's Office",
    description: "Academic consultation, student support, and administrative communication.",
    questions: [
      "The Dean's Office is available when I need consultation or academic advice.",
      "The Dean's Office supports students and recognizes their achievements.",
      "The Dean and staff communicate professionally and clearly.",
    ],
  },
  {
    code: "cir",
    name: "Curriculum, Instruction and Research",
    description: "Curriculum design, teaching quality, and research opportunities.",
    questions: [
      "My courses provide useful learning materials and relevant examples.",
      "My courses provide practical activities and research experiences.",
      "The instructors and personnel provide guidance that helps me develop professional skills.",
    ],
  },
  {
    code: "campus_security",
    name: "Campus Security and Service",
    description: "Safety, security presence, and campus peace and order.",
    questions: [
      "Security personnel are visible and available around the campus.",
      "Security personnel treat students fairly and respectfully.",
      "I feel safe and secure while inside the UDM campus.",
    ],
  },
  {
    code: "physical_facilities",
    name: "Physical Facilities",
    description: "Classrooms, restrooms, common areas, and general maintenance.",
    questions: [
      "Classrooms and learning areas are clean, comfortable, well-lighted, and properly ventilated.",
      "Restrooms and drinking facilities are clean, accessible, and well-maintained.",
      "Common areas such as hallways, gardens, and event venues are clean and well-maintained.",
    ],
  },
  {
    code: "food_service",
    name: "Food Service",
    description: "Canteen food quality, pricing, and dining environment.",
    questions: [
      "The canteen and food service areas are clean and comfortable.",
      "The food offered is affordable, satisfactory, and has enough variety.",
      "Food service staff are friendly, accommodating, and provide clean and safe service.",
    ],
  },
  {
    code: "health_service",
    name: "Health Service",
    description: "Medical clinic, health guidance, and student wellness support.",
    questions: [
      "The clinic provides accessible and readily available health services.",
      "Medical personnel are competent, friendly, and accommodating.",
      "The clinic provides appropriate facilities, privacy, and basic medical services.",
    ],
  },
  {
    code: "library",
    name: "Library",
    description: "Library resources, study environment, and research support.",
    questions: [
      "Library staff are available, friendly, and helpful.",
      "The library provides sufficient learning resources, computers, and internet access.",
      "The library provides a comfortable environment and assistance for studying and research.",
    ],
  },
  {
    code: "community_extension",
    name: "Community Extension",
    description: "Outreach programs, community engagement, and social responsibility.",
    questions: [
      "Community Extension personnel are available, friendly, and accommodating.",
      "UDM provides opportunities for students to participate in community and outreach activities.",
      "Community Extension activities help promote civic awareness and social responsibility.",
    ],
  },
  {
    code: "culture_arts_sports",
    name: "Culture, Arts and Sports",
    description: "Cultural, artistic, and sports development programs and facilities.",
    questions: [
      "UDM provides opportunities for cultural, artistic, and sports activities.",
      "Students are encouraged to participate in cultural, arts, and sports activities.",
      "The personnel handling these activities are available, friendly, and accommodating.",
    ],
  },
  {
    code: "registrar",
    name: "Registrar",
    description: "Document processing, enrollment support, and records management.",
    questions: [
      "The Registrar provides efficient and timely services.",
      "Registrar staff are friendly, accommodating, and responsive to student inquiries.",
      "Registrar procedures, records, and document requests are organized and easy to follow.",
    ],
  },
  {
    code: "guidance_counselling",
    name: "Guidance, Counselling and Psychological Testing",
    description: "Academic guidance, personal counselling, and psychological support.",
    questions: [
      "Guidance and counselling services are accessible when students need them.",
      "Guidance personnel are friendly, accommodating, and respectful of student privacy.",
      "UDM provides useful guidance, counselling, psychological testing, and student development activities.",
    ],
  },
  {
    code: "student_affairs",
    name: "Student Affairs",
    description: "Student services, organizations, discipline, and campus life support.",
    questions: [
      "Student Affairs personnel are accessible, friendly, and accommodating.",
      "Student Affairs supports student organizations, activities, and student achievements.",
      "Student Affairs provides fair and timely services to students.",
    ],
  },
  {
    code: "ms_teams",
    name: "MS Teams Services",
    description: "Learning management, online classes, and digital class support.",
    questions: [
      "MS Teams provides accessible and updated course materials.",
      "MS Teams services allow students to easily upload and download learning materials.",
      "MS Teams support personnel are competent, responsive, and helpful.",
    ],
  },
  {
    code: "ict_services",
    name: "Information, Communication and Technology Services",
    description: "Internet connectivity, campus systems, and technical support.",
    questions: [
      "ICT Services provide accessible and reliable technical support.",
      "ICT personnel respond quickly and are friendly and helpful.",
      "UDM's website and technology services are updated and easy to use.",
    ],
  },
  {
    code: "laboratory",
    name: "Laboratory",
    description: "Laboratory equipment, safety, instruction, and practicum support.",
    questions: [
      "The laboratory is clean, well-ventilated, and suitable for learning.",
      "The laboratory has adequate and functional equipment, tools, and materials.",
      "Laboratory personnel are competent, accessible, and helpful.",
    ],
  },
  {
    code: "gender_development",
    name: "Gender and Development",
    description: "Gender sensitivity, inclusivity, and related advocacy programs.",
    questions: [
      "UDM provides activities and training that promote gender awareness and sensitivity.",
      "Students are given equal opportunities to participate in student organizations and activities.",
      "UDM provides accessible and confidential support for gender-related concerns, harassment, or discrimination.",
    ],
  },
];

export const SERVICE_AREA_CODES = new Set(SERVICE_AREAS.map((item) => item.code));

export const LABORATORY_CODE = "laboratory";

export function get_service_area(code) {
  return SERVICE_AREAS.find((item) => item.code === code) || null;
}

export function get_service_areas() {
  return [...SERVICE_AREAS];
}

export function service_area_choices() {
  return SERVICE_AREAS.map((item) => ({ code: item.code, name: item.name }));
}