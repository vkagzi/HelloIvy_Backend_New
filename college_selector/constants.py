"""
College Selector constants — dropdown/MCQ options from PRD.
"""

DEGREE_LEVELS = [
    ("undergraduate", "Undergraduate"),
    ("postgraduate", "Postgraduate"),
    ("doctorate", "Doctorate"),
]

DEGREE_TYPES_UNDERGRADUATE = [
    "Bachelor of Arts (BA)",
    "Bachelor of Science (BS / BSc)",
    "Bachelor of Fine Arts (BFA)",
    "Bachelor of Music (BM / BMus)",
    "Bachelor of Design (BDes / BDesign)",
    "Bachelor of Architecture (BArch)",
    "Bachelor of Engineering (BE)",
    "Bachelor of Science in Engineering (BSE / BEng)",
    "Bachelor of Technology (BTech)",
    "Bachelor of Commerce (BCom)",
    "Bachelor of Business Administration (BBA)",
    "Bachelor of Management Studies (BMS)",
    "Bachelor of Economics (BEcon / Econ BA/BS)",
    "Bachelor of Social Work (BSW)",
    "Bachelor of Education (BEd)",
    "Bachelor of Journalism / Mass Communication (BJ, BJMC)",
    "Bachelor of Communication",
    "Bachelor of Law (LLB)",
    "Bachelor of Computer Applications (BCA)",
    "Bachelor of Information Technology (BIT / BITech)",
    "Bachelor of Data Science",
    "Bachelor of Artificial Intelligence",
    "Bachelor of Nursing (BSN / BSc Nursing)",
    "Bachelor of Pharmacy (BPharm)",
    "Bachelor of Public Health (BPH)",
    "Bachelor of Physiotherapy (BPT)",
    "Bachelor of Occupational Therapy",
    "Bachelor of Dental Surgery (BDS)",
    "Bachelor of Medicine / MBBS-equivalent entry programs",
    "Bachelor of Veterinary Science",
    "Bachelor of Agriculture (BSc Agriculture)",
    "Bachelor of Environmental Science",
    "Bachelor of Hospitality Management",
    "Bachelor of Hotel Administration",
    "Bachelor of Tourism Management",
    "Bachelor of Culinary Arts",
    "Bachelor of Fashion Technology / Fashion Design",
    "Bachelor of Interior Design",
    "Bachelor of Animation / Game Design",
    "Bachelor of Aviation / Aeronautical Studies",
    "Other",
]

DEGREE_TYPES_POSTGRADUATE = [
    "Master of Arts (MA)",
    "Master of Science (MS / MSc)",
    "Master of Research (MRes)",
    "Master of Studies (MSt)",
    "Master of Liberal Arts (MLA / ALM)",
    "Master of Fine Arts (MFA)",
    "Master of Public Health (MPH)",
    "Master of Education (MEd)",
    "Master of Engineering (MEng / ME / MTech)",
    "Master of Interdisciplinary Studies (MIS / MAIS)",
    "Integrated Master of Engineering (MEng)",
    "Integrated Master of Science (MSci / MSc)",
    "BS/MS in Engineering",
    "BS/MS in Computer Science",
    "BS/MS in Data Science / AI",
    "BS/MS in Biotechnology / Life Sciences",
    "BBA + MBA Integrated Programs",
    "BS/BA + Master in Management (MiM)",
    "Integrated Business Honors + Master's Programs",
    "Finance or Economics Combined Bachelor's + Master's",
    "BA + Master of Public Policy (MPP)",
    "BA + Master of International Relations",
    "BA + Master of Public Administration (MPA)",
    "Integrated Social Sciences Master's Pathways",
    "BA/MA in Humanities",
    "BA/MA in Languages or Literature",
    "Integrated Liberal Arts Master's Programs",
    "Integrated Bachelor + Master of Architecture",
    "Integrated Design Master's Programs",
    "Master of Advanced Study (MAS)",
    "Master of Applied Science (MASc)",
    "Master of Business Administration (MBA)",
    "Executive MBA (EMBA)",
    "Master in Management (MiM / MIM)",
    "Master of Finance (MFin / MiF)",
    "MPhil",
    "Other",
]

DEGREE_TYPES_DOCTORATE = [
    "PhD",
    "Doctor of Philosophy (PhD)",
    "Doctor of Medicine (MD)",
    "Doctor of Education (EdD)",
    "Doctor of Business Administration (DBA)",
    "Doctor of Psychology (PsyD)",
    "Doctor of Public Health (DrPH)",
    "Doctor of Engineering (DEng / EngD)",
    "Juris Doctor (JD)",
    "Other",
]

DEGREE_TYPES_BY_LEVEL = {
    "undergraduate": DEGREE_TYPES_UNDERGRADUATE,
    "postgraduate": DEGREE_TYPES_POSTGRADUATE,
    "doctorate": DEGREE_TYPES_DOCTORATE,
}

MAJOR_OPTIONS = {
    "Business & Economics": [
        "Accounting", "Finance", "Economics", "Business Administration",
        "International Business", "Marketing", "Management", "Entrepreneurship",
        "Supply Chain Management", "Operations Management", "Human Resource Management",
        "Business Analytics", "Management Information Systems", "Actuarial Science",
        "Real Estate", "Hospitality Management", "Luxury Brand Management",
        "Sports Management", "Organizational Behavior", "Behavioral Economics",
    ],
    "Engineering": [
        "Mechanical Engineering", "Electrical Engineering", "Computer Engineering",
        "Civil Engineering", "Chemical Engineering", "Aerospace Engineering",
        "Biomedical Engineering", "Environmental Engineering",
        "Materials Science & Engineering", "Industrial Engineering",
        "Systems Engineering", "Robotics Engineering", "Mechatronics",
        "Nuclear Engineering", "Petroleum Engineering", "Automotive Engineering",
        "Marine Engineering", "Agricultural Engineering", "Structural Engineering",
        "Manufacturing Engineering",
    ],
    "Computer Science & Technology": [
        "Computer Science", "Data Science", "Artificial Intelligence",
        "Machine Learning", "Cybersecurity", "Software Engineering",
        "Information Technology", "Information Systems", "Human-Computer Interaction",
        "Computational Science", "Robotics", "Bioinformatics", "Blockchain",
        "Cloud Computing", "Quantum Computing", "Game Development",
        "Computer Graphics", "Computational Linguistics", "Digital Transformation",
        "Product Management (Tech)",
    ],
    "Natural Sciences": [
        "Physics", "Chemistry", "Biology", "Mathematics", "Statistics",
        "Applied Mathematics", "Biochemistry", "Biotechnology", "Neuroscience",
        "Environmental Science", "Ecology", "Geology", "Earth Sciences",
        "Astronomy", "Astrophysics", "Marine Science", "Genetics",
        "Microbiology", "Molecular Biology", "Cognitive Science",
    ],
    "Social Sciences": [
        "Psychology", "Sociology", "Anthropology", "Political Science",
        "International Relations", "Public Policy", "Public Administration",
        "Development Studies", "Gender Studies", "Urban Studies", "Criminology",
        "Human Geography", "Behavioral Science", "Migration Studies",
        "Peace & Conflict Studies", "Area Studies", "Global Studies",
        "Social Work", "Demography", "Public Affairs",
    ],
    "Humanities & Liberal Arts": [
        "English Literature", "Comparative Literature", "History", "Philosophy",
        "Religious Studies", "Classics", "Linguistics",
        "Languages (French, Spanish, German, etc.)", "Creative Writing", "Ethics",
        "Archaeology", "Cultural Studies", "Rhetoric", "Journalism", "Media Studies",
    ],
    "Health & Medicine": [
        "Pre-Medical Studies", "Public Health", "Biomedical Sciences", "Nursing",
        "Pharmacy", "Kinesiology", "Nutrition", "Epidemiology", "Health Sciences",
        "Occupational Therapy", "Physical Therapy", "Clinical Psychology",
        "Global Health", "Health Policy", "Speech Pathology",
    ],
    "Law & Governance": [
        "Pre-Law", "Legal Studies", "Jurisprudence", "International Law",
        "Human Rights", "Constitutional Studies", "Public Administration",
        "Governance", "Security Studies", "Diplomacy",
    ],
    "Design & Architecture": [
        "Architecture", "Interior Design", "Industrial Design", "Graphic Design",
        "UX/UI Design", "Product Design", "Fashion Design", "Fine Arts",
        "Illustration", "Animation", "Film Studies", "Photography",
        "Visual Arts", "Game Design", "Urban Design", "Landscape Architecture",
    ],
    "Communication & Media": [
        "Communications", "Journalism", "Advertising", "Public Relations",
        "Digital Media", "Film Production", "Screenwriting", "Broadcast Media",
        "Content Strategy", "Media Management",
    ],
    "Education": [
        "Education", "Early Childhood Education", "Secondary Education",
        "Educational Leadership", "Curriculum & Instruction", "Special Education",
        "Learning Sciences", "Education Policy",
    ],
    "Sustainability & Environment": [
        "Sustainability Studies", "Climate Science", "Environmental Policy",
        "Renewable Energy", "Conservation Biology", "Sustainable Development",
        "Energy Systems", "Circular Economy",
    ],
    "Agriculture & Food": [
        "Agriculture", "Food Science", "Agribusiness", "Animal Science",
        "Veterinary Science", "Plant Science", "Horticulture", "Soil Science",
    ],
    "Interdisciplinary & Emerging": [
        "PPE (Philosophy, Politics, Economics)",
        "Science, Technology & Society (STS)", "Cognitive Science",
        "Computational Biology", "Environmental Economics",
        "Mathematical Economics", "Digital Humanities", "Behavioral Economics",
        "Entrepreneurship & Innovation", "Global Health Policy",
        "Ethics, Politics & Economics", "Data + Public Policy", "AI & Society",
        "Human-Centered Design", "Technology Management",
        "Climate Technology", "AI Ethics", "Responsible Innovation",
        "Synthetic Biology", "Quantum Information Science", "Space Studies",
        "Computational Social Science", "Digital Health", "FinTech",
        "Web3 / Decentralized Systems",
    ],
}

# Flattened list of all majors for validation
ALL_MAJORS = []
for category_majors in MAJOR_OPTIONS.values():
    ALL_MAJORS.extend(category_majors)
ALL_MAJORS.append("Other")

COUNTRY_OPTIONS = [
    "United States of America", "United Kingdom", "Canada", "India", "Singapore",
    "Australia", "France", "Spain", "Ireland", "Germany",
    "Netherlands", "New Zealand", "Switzerland", "Sweden", "Denmark",
    "Japan", "South Korea", "Hong Kong", "Italy", "Austria",
    "Belgium", "Finland", "Norway", "Czech Republic", "Poland",
    "Portugal", "United Arab Emirates", "China", "Malaysia", "Thailand",
]

CAMPUS_SETTINGS = [
    ("urban", "Urban (city-based campus with access to internships, culture, nightlife)"),
    ("suburban", "Suburban (balanced campus-town environment)"),
    ("rural", "Rural (traditional campus, quieter and close-knit community)"),
    ("no_preference", "Open to Either / No preference"),
]

CAMPUS_IMPORTANCE = [
    ("must_have", "Must Have"),
    ("nice_to_have", "Nice to Have"),
    ("not_important", "Not Important"),
]

CLIMATE_PREFERENCES = [
    ("warm", "Warm weather"),
    ("four_seasons", "All four seasons"),
    ("cold", "Cold/snowy"),
    ("no_preference", "No preference"),
]

COLLEGE_TYPES = [
    ("public", "Public / State University"),
    ("private", "Private University"),
    ("specialized", "Specialized Institution (Liberal Arts, Tech, Design, Business, etc.)"),
    ("no_preference", "No preference"),
]

COLLEGE_TYPE_REASONS = [
    "Lower tuition",
    "Smaller community",
    "Prestige/reputation",
    "Research opportunities",
    "Strong teaching focus",
]

RESEARCH_IMPORTANCE = [
    ("very_important", "Very Important — I want a research-heavy institution"),
    ("moderately_important", "Moderately Important — Some research access matters"),
    ("low_importance", "Low Importance — I prefer teaching-focused institutions"),
    ("unsure", "Unsure / Open to Recommendations"),
]

RESEARCH_EXPOSURE = [
    "Undergraduate research opportunities",
    "Access to labs and faculty research",
    "Strong PhD/research ecosystem",
    "Industry-led applied research",
    "No preference",
]

CULTURAL_FIT_ACADEMIC = [
    "Collaborative and supportive",
    "Competitive and ambitious",
    "Academically rigorous / intense",
]

CULTURAL_FIT_SOCIAL = [
    "Social and spirited (sports, traditions, campus events)",
    "Diverse and globally minded",
    "Close-knit and community oriented",
]

FIT_IMPORTANCE = [
    ("critical", "Critical"),
    ("important", "Important"),
    ("somewhat_important", "Somewhat Important"),
]

CLASS_SIZE_OPTIONS = [
    ("small", "Small classes (under 20 students)"),
    ("medium", "Medium classes (20–50 students)"),
    ("large", "Large lectures with smaller discussion sections"),
    ("no_preference", "No strong preference"),
]

TEACHING_STYLE_OPTIONS = [
    ("seminar", "Seminar-style discussion"),
    ("personalized", "Personalized faculty attention"),
    ("independent", "Independent/self-directed learning"),
    ("large_ecosystem", "Large university ecosystem with flexibility"),
]
