"""
Management command to create a test user with a complete profile.

This script creates a user with a specific persona profile that can be used
for testing the Stream & Subject Selection flow. The profile includes all fields from
fieldDefinitions.ts and has a clear inclination towards a specific domain.

Usage:
    python manage.py create_test_user_profile --persona arts
    python manage.py create_test_user_profile --persona engineering
    python manage.py create_test_user_profile --persona entrepreneurship
    python manage.py create_test_user_profile --persona science
    python manage.py create_test_user_profile --persona random
    python manage.py create_test_user_profile --email test@example.com --persona arts
    python manage.py create_test_user_profile --persona arts --academic-level undergraduate
    python manage.py create_test_user_profile --email test@example.com --persona engineering --academic-level high_school --grade-level "Grade 10"

"""
import uuid
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import User
from apps.profiles.models import UserProfile


# Available academic levels
ACADEMIC_LEVELS = {
    "high_school": "High School (8th–12th grade)",
    "undergraduate": "College/Undergraduate",
    "postgraduate": "Postgraduate/Master's",
    "professional": "Working Professional"
}

# Grade levels for each academic level
GRADE_LEVELS = {
    "high_school": ["Grade 8", "Grade 9", "Grade 10", "Grade 11", "Grade 12"],
    "undergraduate": ["Year 1", "Year 2", "Year 3", "Year 4"],
    "postgraduate": ["Year 1", "Year 2"],
    "professional": ["1-3 years", "3-5 years", "5+ years"]
}

# Available personas (excluding 'random')
AVAILABLE_PERSONAS = ['arts', 'engineering', 'entrepreneurship', 'science']


# Define different persona profiles
PERSONA_PROFILES = {
    "arts": {
        "description": "A creative student passionate about visual arts, music, and creative expression",
        "academicLevel": "High School (8th–12th grade)",
        "gradeLevel": "Grade 11",
        "personal": {
            "firstName": "Maya",
            "lastName": "Patel",
            "gender": "Female",
            "dob": "2008-03-15",
            "city": "Mumbai",
            "state": "Maharashtra",
            "country": "India",
            "citizenShip": "India",
            "addressline": "123 Creative Arts Lane, Bandra",
            "zipcode": "400050",
            "countryCode": "+91",
            "phoneNumber": "9876543210",
            "fathersProfession": "Graphic Designer",
            "mothersProfession": "Art Gallery Curator",
            "annualIncome": "₹15-20 lakhs",
            "languages": [
                {"language": "English", "type": "Speak", "proficiency": "Advanced", "comment": "Primary language"},
                {"language": "Hindi", "type": "Speak", "proficiency": "Native", "comment": "Mother tongue"}
            ],
            "learningDifficulties": "No learning difficulties",
            "physicalDisabilities": "No, I do not have any physical disability"
        },
        "educational": {
            "academicLevel": "High School (8th–12th grade)",
            "gradeLevel": "Grade 11",
            "schoolName": "National Institute of Creative Arts School",
            "city": "Mumbai",
            "yearOfCompletion": "2026",
            "board": "CBSE",
            "yourTotalScore": "88",
            "highestTotalScore": "100",
            "redFlags": "",
            "subjects": [
                {"subject": "English", "yourTotalScore": "95", "highestTotalScore": "100"},
                {"subject": "History", "yourTotalScore": "92", "highestTotalScore": "100"},
                {"subject": "Economics", "yourTotalScore": "85", "highestTotalScore": "100"},
                {"subject": "Psychology", "yourTotalScore": "90", "highestTotalScore": "100"},
                {"subject": "Sociology", "yourTotalScore": "88", "highestTotalScore": "100"}
            ],
            "courses": [
                {
                    "courseType": "Online Course",
                    "courseLink": "https://coursera.org/digital-art",
                    "awards": "Certificate of Excellence",
                    "description": "Advanced Digital Art and Illustration",
                    "duration": "3 months",
                    "location": "Online"
                }
            ],
            "awards": [
                {
                    "nameOfHonorReceived": "Best Young Artist Award",
                    "description": "Recognized for outstanding creativity in visual arts",
                    "levelOfCompetitiveness": "State",
                    "numberOfParticipants": "500",
                    "year": "2024",
                    "amount": "25000"
                },
                {
                    "nameOfHonorReceived": "Music Composition Winner",
                    "description": "First place in inter-school music competition",
                    "levelOfCompetitiveness": "District",
                    "numberOfParticipants": "150",
                    "year": "2023",
                    "amount": ""
                }
            ],
            "testType": ["SAT"],
            "testDate": "2025-03-15",
            "totalScore": "1380",
            "writingYourScore": "720",
            "writingYourPercentile": "92",
            "mathYourScore": "660",
            "mathYourPercentile": "75"
        },
        "extraCurricular": [
            {
                "activityType": "Arts & Music",
                "startDate": "2020-06-01",
                "endDate": "2025-12-31",
                "positionHeld": "Lead Artist, School Art Club",
                "awardsCertifications": "Best Visual Arts Display 2024",
                "description": "Created murals and organized art exhibitions"
            },
            {
                "activityType": "Clubs & Organizations",
                "startDate": "2022-01-01",
                "endDate": "2025-12-31",
                "positionHeld": "Founder, Creative Writing Club",
                "awardsCertifications": "Published anthology of student poems",
                "description": "Started a creative writing club with 30+ members"
            },
            {
                "activityType": "Community Service",
                "startDate": "2023-06-01",
                "endDate": "2024-06-30",
                "positionHeld": "Art Teacher Volunteer",
                "awardsCertifications": "100 Hours of Service",
                "description": "Taught art to underprivileged children on weekends"
            }
        ],
        "additional": {
            "degreeInterest": "Bachelor of Fine Arts (BFA)",
            "whyInterest": "I want to pursue my passion for visual arts and develop my skills professionally. I dream of becoming a renowned artist or art director.",
            "domainInterest": "Arts & Design",
            "domainWhyInterest": "Art has always been my way of expressing myself. I spend hours drawing, painting, and creating digital art.",
            "shareInformation": "Yes",
            "shareInformationDescription": "I have been drawing since I was 5 years old. My artwork has been featured in local galleries and I have sold several pieces. I also compose music and play piano."
        }
    },
    "engineering": {
        "description": "A STEM-focused student passionate about technology, robotics, and problem-solving",
        "academicLevel": "High School (8th–12th grade)",
        "gradeLevel": "Grade 12",
        "personal": {
            "firstName": "Arjun",
            "lastName": "Sharma",
            "gender": "Male",
            "dob": "2007-08-22",
            "city": "Bangalore",
            "state": "Karnataka",
            "country": "India",
            "citizenShip": "India",
            "addressline": "456 Tech Park Road, Whitefield",
            "zipcode": "560066",
            "countryCode": "+91",
            "phoneNumber": "9123456789",
            "fathersProfession": "Software Engineer at Google",
            "mothersProfession": "Professor of Computer Science",
            "annualIncome": "₹50 lakhs - ₹1 crore",
            "languages": [
                {"language": "English", "type": "Speak", "proficiency": "Advanced", "comment": ""},
                {"language": "Hindi", "type": "Speak", "proficiency": "Advanced", "comment": ""},
                {"language": "Japanese", "type": "Read", "proficiency": "Basic", "comment": "Learning for anime"}
            ],
            "learningDifficulties": "No learning difficulties",
            "physicalDisabilities": "No, I do not have any physical disability"
        },
        "educational": {
            "academicLevel": "High School (8th–12th grade)",
            "gradeLevel": "Grade 12",
            "schoolName": "Delhi Public School, Whitefield",
            "city": "Bangalore",
            "yearOfCompletion": "2025",
            "board": "CBSE",
            "yourTotalScore": "96",
            "highestTotalScore": "100",
            "redFlags": "",
            "subjects": [
                {"subject": "Mathematics", "yourTotalScore": "99", "highestTotalScore": "100"},
                {"subject": "Physics", "yourTotalScore": "97", "highestTotalScore": "100"},
                {"subject": "Chemistry", "yourTotalScore": "94", "highestTotalScore": "100"},
                {"subject": "Computer Science", "yourTotalScore": "100", "highestTotalScore": "100"},
                {"subject": "English", "yourTotalScore": "88", "highestTotalScore": "100"}
            ],
            "courses": [
                {
                    "courseType": "Online Course",
                    "courseLink": "https://coursera.org/machine-learning",
                    "awards": "Certificate with Distinction",
                    "description": "Machine Learning by Andrew Ng",
                    "duration": "4 months",
                    "location": "Online"
                },
                {
                    "courseType": "Bootcamp",
                    "courseLink": "https://mit.edu/xpro",
                    "awards": "Completion Certificate",
                    "description": "MIT Professional Education - Robotics",
                    "duration": "2 months",
                    "location": "Hybrid"
                }
            ],
            "awards": [
                {
                    "nameOfHonorReceived": "National Science Olympiad Gold Medal",
                    "description": "First place in Physics and Mathematics combined",
                    "levelOfCompetitiveness": "National",
                    "numberOfParticipants": "50000",
                    "year": "2024",
                    "amount": "100000"
                },
                {
                    "nameOfHonorReceived": "Robotics World Championship - 3rd Place",
                    "description": "International FIRST Robotics Competition",
                    "levelOfCompetitiveness": "National",
                    "numberOfParticipants": "3000",
                    "year": "2024",
                    "amount": ""
                },
                {
                    "nameOfHonorReceived": "Google Code-In Winner",
                    "description": "Open source contributions to TensorFlow",
                    "levelOfCompetitiveness": "National",
                    "numberOfParticipants": "10000",
                    "year": "2023",
                    "amount": ""
                }
            ],
            "testType": ["SAT", "TOEFL"],
            "testDate": "2024-10-15",
            "totalScore": "1560",
            "writingYourScore": "780",
            "writingYourPercentile": "99",
            "mathYourScore": "800",
            "mathYourPercentile": "99",
            "numberOfAttempts": "1"
        },
        "extraCurricular": [
            {
                "activityType": "Clubs & Organizations",
                "startDate": "2020-06-01",
                "endDate": "2025-12-31",
                "positionHeld": "President, Robotics Club",
                "awardsCertifications": "Built 5 award-winning robots",
                "description": "Founded and led school robotics club, mentored 50+ students"
            },
            {
                "activityType": "Research",
                "startDate": "2023-06-01",
                "endDate": "2024-08-31",
                "positionHeld": "Research Intern at IISc",
                "awardsCertifications": "Co-authored paper on ML algorithms",
                "description": "Summer research on neural network optimization"
            },
            {
                "activityType": "Academic Competitions",
                "startDate": "2021-01-01",
                "endDate": "2025-12-31",
                "positionHeld": "Team Captain, Math Olympiad Team",
                "awardsCertifications": "Multiple national and state level awards",
                "description": "Represented school in national mathematics competitions"
            },
            {
                "activityType": "Entrepreneurship",
                "startDate": "2023-01-01",
                "endDate": "2025-12-31",
                "positionHeld": "Co-founder, EduTech Startup",
                "awardsCertifications": "Seed funding from school incubator",
                "description": "Built an AI-powered tutoring app with 1000+ users"
            }
        ],
        "additional": {
            "degreeInterest": "Bachelor of Science (BS)",
            "whyInterest": "I want to study Computer Science and AI at a top university to become a researcher in artificial intelligence.",
            "domainInterest": "Technology & IT",
            "domainWhyInterest": "I've been coding since I was 10. I love building things that solve real problems. Technology is the future and I want to be at the forefront.",
            "shareInformation": "Yes",
            "shareInformationDescription": "I've built several apps including one that helps visually impaired people navigate. I contribute to open source projects and have 500+ GitHub stars. My dream is to work on AGI research."
        }
    },
    "entrepreneurship": {
        "description": "A business-minded student passionate about startups, leadership, and creating impact",
        "academicLevel": "College/Undergraduate",
        "gradeLevel": "Year 3",
        "personal": {
            "firstName": "Priya",
            "lastName": "Mehta",
            "gender": "Female",
            "dob": "2004-11-08",
            "city": "Delhi",
            "state": "Delhi",
            "country": "India",
            "citizenShip": "India",
            "addressline": "789 Entrepreneurship Hub, Connaught Place",
            "zipcode": "110001",
            "countryCode": "+91",
            "phoneNumber": "9988776655",
            "fathersProfession": "Business Owner - Textile Industry",
            "mothersProfession": "Investment Banker",
            "annualIncome": "Above ₹1 crore",
            "languages": [
                {"language": "English", "type": "Speak", "proficiency": "Native", "comment": ""},
                {"language": "Hindi", "type": "Speak", "proficiency": "Native", "comment": ""},
                {"language": "French", "type": "Speak", "proficiency": "Intermediate", "comment": ""}
            ],
            "learningDifficulties": "No learning difficulties",
            "physicalDisabilities": "No, I do not have any physical disability"
        },
        "educational": {
            "academicLevel": "College/Undergraduate",
            "gradeLevel": "Year 3",
            "institutionName": "Shri Ram College of Commerce",
            "degree": "B.Com (Bachelor of Commerce)",
            "major": "Business Studies",
            "startYear": "2022",
            "endYear": "2025",
            "overallPercentage": "8.9",
            "maximumPossibleGPA": "10",
            "estimatedRank": "15",
            "redFlags": "",
            "years": [
                {"score": "8.5", "highestTotalScore": "10"},
                {"score": "9.0", "highestTotalScore": "10"},
                {"score": "9.2", "highestTotalScore": "10"}
            ],
            "courses": [
                {
                    "courseType": "Professional Certification",
                    "courseLink": "https://hbs.edu/online",
                    "awards": "Certificate of Completion",
                    "description": "Harvard Business School Online - Disruptive Strategy",
                    "duration": "6 weeks",
                    "location": "Online"
                },
                {
                    "courseType": "Bootcamp",
                    "courseLink": "https://ycombinator.com/startup-school",
                    "awards": "Graduate",
                    "description": "Y Combinator Startup School",
                    "duration": "10 weeks",
                    "location": "Online"
                }
            ],
            "awards": [
                {
                    "nameOfHonorReceived": "E-Summit Business Plan Winner",
                    "description": "First place among 200 teams at IIT Delhi E-Summit",
                    "levelOfCompetitiveness": "National",
                    "numberOfParticipants": "1000",
                    "year": "2024",
                    "amount": "500000"
                },
                {
                    "nameOfHonorReceived": "Forbes 30 Under 30 - Student Entrepreneur",
                    "description": "Recognized for social enterprise impact",
                    "levelOfCompetitiveness": "National",
                    "numberOfParticipants": "10000",
                    "year": "2024",
                    "amount": ""
                }
            ],
            "testType": ["GMAT"],
            "testDate": "2024-06-15",
            "totalScore": "720",
            "verbalReasoningScore": "42",
            "verbalReasoningPercentile": "96",
            "quantitativeReasoningScore": "49",
            "quantitativeReasoningPercentile": "74",
            "dataInsightsScore": "7",
            "dataInsightsPercentile": "89"
        },
        "extraCurricular": [
            {
                "activityType": "Entrepreneurship",
                "startDate": "2022-06-01",
                "endDate": "2025-12-31",
                "positionHeld": "Founder & CEO, EcoPackage Solutions",
                "awardsCertifications": "Raised $50K seed funding",
                "description": "Sustainable packaging startup with 20+ B2B clients"
            },
            {
                "activityType": "Leadership Programs",
                "startDate": "2023-01-01",
                "endDate": "2024-12-31",
                "positionHeld": "President, Entrepreneurship Cell",
                "awardsCertifications": "Organized E-Summit with 5000 attendees",
                "description": "Led 50-member team, managed ₹15L budget"
            },
            {
                "activityType": "Clubs & Organizations",
                "startDate": "2022-08-01",
                "endDate": "2025-12-31",
                "positionHeld": "Vice President, Debate Society",
                "awardsCertifications": "Best Speaker, National Debate Championship",
                "description": "Won 10+ inter-college debate competitions"
            },
            {
                "activityType": "Volunteer Work",
                "startDate": "2021-06-01",
                "endDate": "2023-12-31",
                "positionHeld": "Youth Ambassador, UN Global Compact",
                "awardsCertifications": "SDG Leadership Award",
                "description": "Promoted sustainable business practices among youth"
            }
        ],
        "additional": {
            "degreeInterest": "Master of Business Administration (MBA)",
            "whyInterest": "I want to pursue an MBA from a top global school to expand my network and skills for scaling my venture internationally.",
            "domainInterest": "Business & Management",
            "domainWhyInterest": "I've been entrepreneurial since I was 15, selling handmade candles. Business is in my blood - I want to build companies that create impact.",
            "shareInformation": "Yes",
            "shareInformationDescription": "I've already built and sold a small business and currently run a sustainable packaging company. I've been featured in YourStory and Economic Times for my work. My goal is to build a unicorn that solves environmental problems."
        }
    },
    "science": {
        "description": "A research-oriented student passionate about scientific discovery and academic research",
        "academicLevel": "College/Undergraduate",
        "gradeLevel": "Year 2",
        "personal": {
            "firstName": "Rahul",
            "lastName": "Krishnan",
            "gender": "Male",
            "dob": "2005-04-12",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "country": "India",
            "citizenShip": "India",
            "addressline": "321 Research Avenue, Anna Nagar",
            "zipcode": "600040",
            "countryCode": "+91",
            "phoneNumber": "9776655443",
            "fathersProfession": "Research Scientist at ISRO",
            "mothersProfession": "Professor of Biochemistry",
            "annualIncome": "₹25-50 lakhs",
            "languages": [
                {"language": "English", "type": "Speak", "proficiency": "Advanced", "comment": ""},
                {"language": "Tamil", "type": "Speak", "proficiency": "Native", "comment": ""}
            ],
            "learningDifficulties": "No learning difficulties",
            "physicalDisabilities": "No, I do not have any physical disability"
        },
        "educational": {
            "academicLevel": "College/Undergraduate",
            "gradeLevel": "Year 2",
            "institutionName": "Indian Institute of Science (IISc)",
            "degree": "B.Sc (Bachelor of Science)",
            "major": "Physics",
            "startYear": "2023",
            "endYear": "2027",
            "overallPercentage": "9.4",
            "maximumPossibleGPA": "10",
            "estimatedRank": "3",
            "redFlags": "",
            "years": [
                {"score": "9.2", "highestTotalScore": "10"},
                {"score": "9.6", "highestTotalScore": "10"}
            ],
            "courses": [
                {
                    "courseType": "MOOCs (Coursera, edX, Udemy)",
                    "courseLink": "https://edx.org/quantum-mechanics",
                    "awards": "Verified Certificate",
                    "description": "MIT Quantum Mechanics Series",
                    "duration": "6 months",
                    "location": "Online"
                },
                {
                    "courseType": "Short-term Course",
                    "courseLink": "https://iisc.ac.in/summer-research",
                    "awards": "Best Project Award",
                    "description": "Summer Research Program in Astrophysics",
                    "duration": "2 months",
                    "location": "On-site"
                }
            ],
            "awards": [
                {
                    "nameOfHonorReceived": "KVPY Fellow",
                    "description": "Kishore Vaigyanik Protsahan Yojana scholarship recipient",
                    "levelOfCompetitiveness": "National",
                    "numberOfParticipants": "100000",
                    "year": "2022",
                    "amount": "80000"
                },
                {
                    "nameOfHonorReceived": "International Physics Olympiad - Silver Medal",
                    "description": "Represented India at IPhO",
                    "levelOfCompetitiveness": "National",
                    "numberOfParticipants": "20000",
                    "year": "2023",
                    "amount": ""
                },
                {
                    "nameOfHonorReceived": "INSPIRE Scholar",
                    "description": "Department of Science & Technology scholarship",
                    "levelOfCompetitiveness": "National",
                    "numberOfParticipants": "500000",
                    "year": "2023",
                    "amount": "100000"
                }
            ],
            "testType": ["GRE"],
            "testDate": "2025-01-15",
            "totalScore": "335",
            "verbalReasoningScore": "165",
            "verbalReasoningPercentile": "96",
            "quantitativeReasoningScore": "170",
            "quantitativeReasoningPercentile": "97",
            "analyticalWritingScore": "5",
            "analyticalWritingPercentile": "92"
        },
        "extraCurricular": [
            {
                "activityType": "Research",
                "startDate": "2023-06-01",
                "endDate": "2025-12-31",
                "positionHeld": "Research Assistant - Quantum Lab",
                "awardsCertifications": "Co-authored paper in Nature Physics",
                "description": "Research on quantum entanglement under Prof. Ramesh"
            },
            {
                "activityType": "Academic Competitions",
                "startDate": "2019-01-01",
                "endDate": "2023-12-31",
                "positionHeld": "Team Captain, Physics Olympiad Team",
                "awardsCertifications": "Multiple international medals",
                "description": "Trained and led national physics olympiad team"
            },
            {
                "activityType": "Clubs & Organizations",
                "startDate": "2023-08-01",
                "endDate": "2025-12-31",
                "positionHeld": "Secretary, Science Club",
                "awardsCertifications": "Organized Nobel Laureate lectures",
                "description": "Organized science talks and experiments for school students"
            },
            {
                "activityType": "Volunteer Work",
                "startDate": "2022-01-01",
                "endDate": "2024-12-31",
                "positionHeld": "Science Educator, Agastya Foundation",
                "awardsCertifications": "Outstanding Volunteer Award",
                "description": "Taught science to rural school children using hands-on experiments"
            }
        ],
        "additional": {
            "degreeInterest": "Doctor of Philosophy (PhD)",
            "whyInterest": "I want to pursue a PhD in Theoretical Physics to contribute to our understanding of the universe. My dream is to work on quantum gravity.",
            "domainInterest": "Science & Research",
            "domainWhyInterest": "I've been fascinated by how the universe works since childhood. Reading Feynman and Hawking changed my life. Pure science is my calling.",
            "shareInformation": "Yes",
            "shareInformationDescription": "I've published a paper as an undergrad and am working on my second. I spend weekends at the observatory and have discovered an asteroid. I want to be a professor and researcher, inspiring the next generation of scientists."
        }
    }
}


class Command(BaseCommand):
    help = 'Create a test user with a complete profile based on a specific persona'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email for the test user (default: <persona>_test@helloivy.com)',
        )
        parser.add_argument(
            '--persona',
            type=str,
            choices=['arts', 'engineering', 'entrepreneurship', 'science', 'random'],
            default='arts',
            help='The persona/inclination for the user profile (use "random" for a randomly selected persona)',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='TestPassword123!',
            help='Password for the test user',
        )
        parser.add_argument(
            '--academic-level',
            type=str,
            choices=['high_school', 'undergraduate', 'postgraduate', 'professional'],
            help='Override the academic level (high_school, undergraduate, postgraduate, professional)',
        )
        parser.add_argument(
            '--grade-level',
            type=str,
            help='Override the grade level (e.g., "Grade 11", "Year 2")',
        )
        parser.add_argument(
            '--list-personas',
            action='store_true',
            help='List all available personas and their descriptions',
        )

    def handle(self, *args, **options):
        if options['list_personas']:
            self.stdout.write(self.style.SUCCESS("\nAvailable Personas:"))
            self.stdout.write("=" * 60)
            for persona_name, persona_data in PERSONA_PROFILES.items():
                self.stdout.write(f"\n{persona_name.upper()}")
                self.stdout.write(f"  Description: {persona_data['description']}")
                self.stdout.write(f"  Academic Level: {persona_data['academicLevel']}")
            self.stdout.write("\nRANDOM")
            self.stdout.write("  Description: Randomly selects one of the above personas")
            self.stdout.write("\nAvailable Academic Levels:")
            for key, value in ACADEMIC_LEVELS.items():
                self.stdout.write(f"  {key}: {value}")
            self.stdout.write("")
            return

        persona = options['persona']

        # Resolve 'random' to an actual persona
        if persona == 'random':
            persona = random.choice(AVAILABLE_PERSONAS)
            self.stdout.write(self.style.WARNING(f"Randomly selected persona: {persona.upper()}"))

        email = options['email'] or f"{persona}_test@helloivy.com"
        password = options['password']
        academic_level_override = options.get('academic_level')
        grade_level_override = options.get('grade_level')

        if persona not in PERSONA_PROFILES:
            self.stdout.write(self.style.ERROR(f"Invalid persona: {persona}"))
            return

        # Make a copy to avoid modifying the original
        import copy
        persona_data = copy.deepcopy(PERSONA_PROFILES[persona])

        # Apply academic level override if provided
        if academic_level_override:
            new_academic_level = ACADEMIC_LEVELS.get(academic_level_override)
            if new_academic_level:
                persona_data['academicLevel'] = new_academic_level
                persona_data['educational']['academicLevel'] = new_academic_level

                # Set a default grade level if not overridden
                if not grade_level_override:
                    grade_level_override = GRADE_LEVELS[academic_level_override][0]

                self.stdout.write(self.style.WARNING(f"Academic level overridden to: {new_academic_level}"))

        # Apply grade level override if provided
        if grade_level_override:
            persona_data['gradeLevel'] = grade_level_override
            persona_data['educational']['gradeLevel'] = grade_level_override
            self.stdout.write(self.style.WARNING(f"Grade level overridden to: {grade_level_override}"))

        self.stdout.write(f"\nCreating test user with persona: {persona.upper()}")
        self.stdout.write(f"  Description: {persona_data['description']}")
        self.stdout.write(f"  Email: {email}")
        self.stdout.write("=" * 60)

        # Check if user already exists
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            self.stdout.write(self.style.WARNING(f"User {email} already exists. Updating profile..."))
            user = existing_user
        else:
            # Create new user
            user = User(email=email)
            user.set_password(password)
            user.is_active = True
            user.terms_accepted = True
            user.terms_accepted_at = timezone.now()
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created user: {email}"))

        # Build the complete profile JSON
        profile_json = self._build_profile_json(persona_data)

        # Create or update profile
        profile, created = UserProfile.objects.update_or_create(
            user_id=user.id,
            defaults={'profile_json': profile_json}
        )

        if created:
            self.stdout.write(self.style.SUCCESS("Created new profile"))
        else:
            self.stdout.write(self.style.SUCCESS("Updated existing profile"))

        # Print summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Profile Summary:"))
        personal = persona_data['personal']
        self.stdout.write(f"  Name: {personal['firstName']} {personal['lastName']}")
        self.stdout.write(f"  Academic Level: {persona_data['academicLevel']}")
        self.stdout.write(f"  Location: {personal['city']}, {personal['country']}")
        
        additional = persona_data.get('additional', {})
        self.stdout.write(f"  Degree Interest: {additional.get('degreeInterest', 'N/A')}")
        self.stdout.write(f"  Domain Interest: {additional.get('domainInterest', 'N/A')}")
        
        extra = persona_data.get('extraCurricular', [])
        self.stdout.write(f"  Extra-curricular Activities: {len(extra)}")
        
        educational = persona_data.get('educational', {})
        courses = educational.get('courses', [])
        awards = educational.get('awards', [])
        self.stdout.write(f"  Courses: {len(courses)}")
        self.stdout.write(f"  Awards: {len(awards)}")
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"\n✓ Test user created successfully!"))
        self.stdout.write(f"  User ID: {user.id}")
        self.stdout.write(f"  Email: {email}")
        self.stdout.write(f"  Password: {password}")
        self.stdout.write(f"  Persona: {persona}")
        self.stdout.write("")

    def _build_profile_json(self, persona_data):
        """Build the complete profile JSON from persona data"""
        personal = persona_data.get('personal', {})
        educational = persona_data.get('educational', {})
        extra_curricular = persona_data.get('extraCurricular', [])
        additional = persona_data.get('additional', {})

        profile = {
            "personalDetails": {
                "firstName": personal.get("firstName", ""),
                "lastName": personal.get("lastName", ""),
                "gender": personal.get("gender", ""),
                "dob": personal.get("dob", ""),
                "countryCode": personal.get("countryCode", "+91"),
                "phoneNumber": personal.get("phoneNumber", ""),
                "addressline": personal.get("addressline", ""),
                "city": personal.get("city", ""),
                "state": personal.get("state", ""),
                "country": personal.get("country", "India"),
                "zipcode": personal.get("zipcode", ""),
                "citizenShip": personal.get("citizenShip", "India"),
                "fathersProfession": personal.get("fathersProfession", ""),
                "mothersProfession": personal.get("mothersProfession", ""),
                "annualIncome": personal.get("annualIncome", ""),
                "languages": personal.get("languages", []),
                "learningDifficulties": personal.get("learningDifficulties", "No learning difficulties"),
                "learningDifficultiesComments": personal.get("learningDifficultiesComments", ""),
                "physicalDisabilities": personal.get("physicalDisabilities", "No, I do not have any physical disability"),
                "physicalDisabilitiesComments": personal.get("physicalDisabilitiesComments", "")
            },
            "educational": {
                "academicLevel": educational.get("academicLevel", ""),
                "gradeLevel": educational.get("gradeLevel", ""),
                # High school fields
                "schoolName": educational.get("schoolName", ""),
                "city": educational.get("city", ""),
                "yearOfCompletion": educational.get("yearOfCompletion", ""),
                "board": educational.get("board", ""),
                "yourTotalScore": educational.get("yourTotalScore", ""),
                "highestTotalScore": educational.get("highestTotalScore", ""),
                "redFlags": educational.get("redFlags", ""),
                "subjects": educational.get("subjects", []),
                # Undergraduate/Postgraduate fields
                "institutionName": educational.get("institutionName", ""),
                "degree": educational.get("degree", ""),
                "major": educational.get("major", ""),
                "startYear": educational.get("startYear", ""),
                "endYear": educational.get("endYear", ""),
                "overallPercentage": educational.get("overallPercentage", ""),
                "maximumPossibleGPA": educational.get("maximumPossibleGPA", ""),
                "estimatedRank": educational.get("estimatedRank", ""),
                "years": educational.get("years", []),
                # Courses and awards
                "courses": educational.get("courses", []),
                "awards": educational.get("awards", []),
                # Standardized test scores
                "testType": educational.get("testType", []),
                "testDate": educational.get("testDate", ""),
                "totalScore": educational.get("totalScore", ""),
                # SAT specific
                "writingYourScore": educational.get("writingYourScore", ""),
                "writingYourPercentile": educational.get("writingYourPercentile", ""),
                "mathYourScore": educational.get("mathYourScore", ""),
                "mathYourPercentile": educational.get("mathYourPercentile", ""),
                "criticalReadingYourScore": educational.get("criticalReadingYourScore", ""),
                "criticalReadingYourPercentile": educational.get("criticalReadingYourPercentile", ""),
                # GRE/GMAT specific
                "analyticalWritingScore": educational.get("analyticalWritingScore", ""),
                "analyticalWritingPercentile": educational.get("analyticalWritingPercentile", ""),
                "verbalReasoningScore": educational.get("verbalReasoningScore", ""),
                "verbalReasoningPercentile": educational.get("verbalReasoningPercentile", ""),
                "quantitativeReasoningScore": educational.get("quantitativeReasoningScore", ""),
                "quantitativeReasoningPercentile": educational.get("quantitativeReasoningPercentile", ""),
                "dataInsightsScore": educational.get("dataInsightsScore", ""),
                "dataInsightsPercentile": educational.get("dataInsightsPercentile", ""),
                # Common
                "retakeExamDate": educational.get("retakeExamDate", ""),
                "numberOfAttempts": educational.get("numberOfAttempts", ""),
                "tookCoaching": educational.get("tookCoaching", ""),
                "coachingName": educational.get("coachingName", "")
            },
            "extraCurricular": extra_curricular,
            "additional": {
                "degreeInterest": additional.get("degreeInterest", ""),
                "whyInterest": additional.get("whyInterest", ""),
                "domainInterest": additional.get("domainInterest", ""),
                "domainWhyInterest": additional.get("domainWhyInterest", ""),
                "shareInformation": additional.get("shareInformation", "No"),
                "shareInformationDescription": additional.get("shareInformationDescription", "")
            }
        }

        return {'profile': profile }
