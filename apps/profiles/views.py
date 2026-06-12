import json
import io
import base64
import os
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from utils.user_dto_view import UserDTOView
from apps.accounts.permissions import RolePermission
from apps.accounts.authentication import CustomJWTAuthentication
from .services import update_user_profile, calculate_profile_completion
from .services import enrich_profile_data
from apps.accounts.models import User
import pdfminer.high_level
from .services import is_profile_complete
from openai import AzureOpenAI
from django.conf import settings

# import docx
import fitz # PyMuPDF
import easyocr
import numpy as np
import cv2
from PIL import Image as PILImage

# Removed docx extraction as it is no longer supported

client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version="2024-02-15-preview"
)

ALLOWED_BOARDS = [
    "American (AP / US High School Diploma)",
    "Cambridge - A Levels",
    "Cambridge - IGCSE",
    "CBSE",
    "HSC",
    "IBCP",
    "ICSE",
    "International Baccalaureate (IB)",
    "ISC",
    "MYP",
    "NIOS",
    "State Board",
    "Other",
]

def normalize_board(board_name: str) -> tuple[str, str | None]:
    """
    Normalizes board name to match one of the standard options.
    Returns a tuple: (normalized_board_name, board_other_value)
    """
    if not board_name or not isinstance(board_name, str):
        return "Other", None

    board_clean = board_name.strip()

    # Direct match (case-insensitive)
    for b in ALLOWED_BOARDS:
        if b.lower() == board_clean.lower():
            return b, None

    # Handle abbreviations and variations
    board_upper = board_clean.upper()

    # 1. Handle MYP and IBCP first
    if board_upper in ["MYP", "IB-MYP", "IB MYP", "IBMYP"]:
        return "MYP", None
    if board_upper in ["IBCP", "IB-CP", "IB CP", "IBCP"]:
        return "IBCP", None

    # 2. International Baccalaureate (IB)
    if (
        board_upper in ["IB", "INTERNATIONAL BACCALAUREATE", "INTERNATIONAL BACCALAUREATE (IB)"]
        or board_upper.startswith("IB-")
        or board_upper.startswith("IB ")
        or board_upper.startswith("IBDP")
        or "INTERNATIONAL BACCALAUREATE" in board_upper
    ):
        return "International Baccalaureate (IB)", None

    # 2. CBSE
    if (
        "CBSE" in board_upper
        or "CENTRAL BOARD" in board_upper
        or "CENTRALBOARD" in board_upper
    ):
        return "CBSE", None

    # 3. ICSE
    if (
        "ICSE" in board_upper
        or "INDIAN CERTIFICATE OF SECONDARY EDUCATION" in board_upper
    ):
        return "ICSE", None

    # 4. ISC
    if (
        "ISC" in board_upper
        or "INDIAN SCHOOL CERTIFICATE" in board_upper
    ):
        return "ISC", None

    # 5. NIOS
    if (
        "NIOS" in board_upper
        or "NATIONAL INSTITUTE OF OPEN" in board_upper
        or "NATIONAL INSTITUTE OF OPEN SCHOOLING" in board_upper
    ):
        return "NIOS", None

    # 6. HSC
    if (
        "HSC" in board_upper
        or "HIGHER SECONDARY CERTIFICATE" in board_upper
        or "HIGHER SECONDARY SCHOOL" in board_upper
    ):
        # Prevent false positives with state board names that might contain HSC as a substring or suffix,
        # but HSC itself is a standard dropdown option
        return "HSC", None

    # 7. Cambridge - IGCSE & A Levels
    if "IGCSE" in board_upper:
        return "Cambridge - IGCSE", None
    if (
        "A LEVEL" in board_upper 
        or "A-LEVEL" in board_upper
        or "A_LEVEL" in board_upper
    ):
        return "Cambridge - A Levels", None
    if "CAMBRIDGE" in board_upper:
        if "IGCSE" in board_upper:
            return "Cambridge - IGCSE", None
        else:
            return "Cambridge - A Levels", None

    # 8. American (AP / US High School Diploma)
    if (
        "AMERICAN" in board_upper
        or "US HIGH SCHOOL" in board_upper
        or "US DIPLOMA" in board_upper
        or "HIGH SCHOOL DIPLOMA" in board_upper
        or "AMERICAN DIPLOMA" in board_upper
        or "ADVANCED PLACEMENT" in board_upper
        or board_upper == "AP"
        or " AP " in board_upper
        or board_upper.startswith("AP ")
        or board_upper.endswith(" AP")
        or board_upper.startswith("AP-")
    ):
        return "American (AP / US High School Diploma)", None

    # 9. State Board
    # Check common state names or abbreviations
    state_keywords = [
        "STATE", "BOARD OF SECONDARY", "BOARD OF INTERMEDIATE", "SECONDARY SCHOOL EDUCATION",
        "MAHARASHTRA", "GUJARAT", "KARNATAKA", "TAMIL NADU", "ANDHRA", "TELANGANA",
        "UTTAR PRADESH", "PUNJAB", "HARYANA", "BIHAR", "WEST BENGAL", "RAJASTHAN",
        "MADHYA PRADESH", "KERALA", "DELHI STATE", "GOA", "UPMSP", "GSEB", "MSBSHSE",
        "KSEEB", "BSEB", "WBBSE", "BSER", "MPBSE", "DHSE", "BIEAP", "BSEAP", "TSBIE"
    ]
    if any(keyword in board_upper for keyword in state_keywords):
        return "State Board", None

    # If no mapping was successful, return 'Other' and the original name for boardOther
    return "Other", board_clean


def normalize_degree(degree_name: str) -> tuple[str, str | None]:
    if not degree_name or not isinstance(degree_name, str):
        return "Other", None
    
    deg_clean = degree_name.strip()
    
    # Direct match (case-insensitive)
    for d in ALLOWED_DEGREES:
        if d.lower() == deg_clean.lower():
            return d, None
            
    # Abbreviation checks
    deg_upper = deg_clean.upper().replace(".", "") # Remove dots for easy match like B.Tech -> BTech
    
    # Common mappings
    # Undergrad
    if deg_upper in ["BA", "BACHELOR OF ARTS"]:
        return "B.A. (Bachelor of Arts)", None
    if deg_upper in ["BARCH", "BACHELOR OF ARCHITECTURE"]:
        return "B.Arch (Bachelor of Architecture)", None
    if deg_upper in ["BBA", "BACHELOR OF BUSINESS ADMINISTRATION", "BACHELOR OF BUSINESS"]:
        return "B.B.A. (Bachelor of Business Administration)", None
    if deg_upper in ["BCA", "BACHELOR OF COMPUTER APPLICATIONS", "BACHELOR OF COMPUTER APPLICATION"]:
        return "B.C.A. (Bachelor of Computer Applications)", None
    if deg_upper in ["BCOM", "BACHELOR OF COMMERCE"]:
        return "B.Com (Bachelor of Commerce)", None
    if deg_upper in ["BDS", "BACHELOR OF DENTAL SURGERY"]:
        return "B.D.S. (Bachelor of Dental Surgery)", None
    if deg_upper in ["BDES", "BACHELOR OF DESIGN"]:
        return "B.Des (Bachelor of Design)", None
    if deg_upper in ["BE", "BACHELOR OF ENGINEERING"]:
        return "B.E. (Bachelor of Engineering)", None
    if deg_upper in ["BED", "BACHELOR OF EDUCATION"]:
        return "B.Ed (Bachelor of Education)", None
    if deg_upper in ["BFA", "BACHELOR OF FINE ARTS"]:
        return "B.F.A. (Bachelor of Fine Arts)", None
    if deg_upper in ["BJ", "BACHELOR OF JOURNALISM"]:
        return "B.J. (Bachelor of Journalism)", None
    if deg_upper in ["LLB", "BL", "BACHELOR OF LAWS", "BACHELOR OF LAW"]:
        return "B.L.L.B. (Bachelor of Laws)", None
    if deg_upper in ["MBBS", "BACHELOR OF MEDICINE"]:
        return "B.M.B.B.S. (Bachelor of Medicine & Surgery)", None
    if deg_upper in ["BSC", "BACHELOR OF SCIENCE"]:
        return "B.Sc (Bachelor of Science)", None
    if deg_upper in ["BTECH", "BT", "BACHELOR OF TECHNOLOGY"]:
        return "B.T. (Bachelor of Technology)", None
        
    # Postgrad
    if deg_upper in ["LLM", "MASTER OF LAWS", "MASTER OF LAW"]:
        return "LL.M. (Master of Laws)", None
    if deg_upper in ["MA", "MASTER OF ARTS"]:
        return "M.A. (Master of Arts)", None
    if deg_upper in ["MARCH", "MASTER OF ARCHITECTURE"]:
        return "M.Arch (Master of Architecture)", None
    if deg_upper in ["MBA", "MASTER OF BUSINESS ADMINISTRATION"]:
        return "M.B.A. (Master of Business Administration)", None
    if deg_upper in ["MCA", "MASTER OF COMPUTER APPLICATIONS", "MASTER OF COMPUTER APPLICATION"]:
        return "M.C.A. (Master of Computer Applications)", None
    if deg_upper in ["MCOM", "MASTER OF COMMERCE"]:
        return "M.Com (Master of Commerce)", None
    if deg_upper in ["MDS", "MASTER OF DENTAL SURGERY"]:
        return "M.D.S. (Master of Dental Surgery)", None
    if deg_upper in ["MDES", "MASTER OF DESIGN"]:
        return "M.Des (Master of Design)", None
    if deg_upper in ["ME", "MASTER OF ENGINEERING"]:
        return "M.E. (Master of Engineering)", None
    if deg_upper in ["MED", "MASTER OF EDUCATION"]:
        return "M.Ed (Master of Education)", None
    if deg_upper in ["MFA", "MASTER OF FINE ARTS"]:
        return "M.F.A. (Master of Fine Arts)", None
    if deg_upper in ["MPT", "MASTER OF PHYSIOTHERAPY"]:
        return "M.P.T. (Master of Physiotherapy)", None
    if deg_upper in ["MSW", "MASTER OF SOCIAL WORK"]:
        return "M.S.W. (Master of Social Work)", None
    if deg_upper in ["MSC", "MS", "MASTER OF SCIENCE"]:
        return "Master of Science (MS / MSc)", None
    if deg_upper in ["MTECH", "MASTER OF TECHNOLOGY"]:
        return "M.Tech (Master of Technology)", None
    if deg_upper in ["PHD", "DOCTOR OF PHILOSOPHY"]:
        return "Ph.D. (Doctor of Philosophy)", None
    if deg_upper in ["MD", "DOCTOR OF MEDICINE"]:
        return "M.D. (Doctor of Medicine)", None

    return "Other", deg_clean

ALLOWED_DEGREES = [
    # Undergraduate
    "B.A. (Bachelor of Arts)",
    "B.Arch (Bachelor of Architecture)",
    "B.B.A. (Bachelor of Business Administration)",
    "B.C.A. (Bachelor of Computer Applications)",
    "B.Com (Bachelor of Commerce)",
    "B.D.S. (Bachelor of Dental Surgery)",
    "B.Des (Bachelor of Design)",
    "B.E. (Bachelor of Engineering)",
    "B.Ed (Bachelor of Education)",
    "B.F.A. (Bachelor of Fine Arts)",
    "B.J. (Bachelor of Journalism)",
    "B.L.L.B. (Bachelor of Laws)",
    "B.M.B.B.S. (Bachelor of Medicine & Surgery)",
    "B.N. (Bachelor of Nursing)",
    "B.P.T. (Bachelor of Physiotherapy)",
    "B.Pharm (Bachelor of Pharmacy)",
    "B.Sc (Bachelor of Science)",
    "B.T. (Bachelor of Technology)",
    "B.V.Sc (Bachelor of Veterinary Science)",
    
    # Postgraduate
    "LL.M. (Master of Laws)",
    "M.A. (Master of Arts)",
    "M.Arch (Master of Architecture)",
    "M.B.A. (Master of Business Administration)",
    "M.C.A. (Master of Computer Applications)",
    "M.Com (Master of Commerce)",
    "M.D.S. (Master of Dental Surgery)",
    "M.Des (Master of Design)",
    "M.E. (Master of Engineering)",
    "M.Ed (Master of Education)",
    "M.F.A. (Master of Fine Arts)",
    "M.L.L.B. (Master of Laws)",
    "M.P.T. (Master of Physiotherapy)",
    "M.Pharm (Master of Pharmacy)",
    "M.S.W. (Master of Social Work)",
    "M.Sc (Master of Science)",
    "M.Tech (Master of Technology)",
    "Master of Arts (MA)",
    "Master of Science (MS / MSc)",
    "Master of Research (MRes)",
    "Master of Studies (MSt)",
    "Master of Liberal Arts (MLA / ALM)",
    "Master of Interdisciplinary Studies (MIS / MAIS)",
    "Master of Advanced Study (MAS)",
    "Master of Applied Science (MASc)",
    "Executive MBA (EMBA)",
    "Master in Management (MiM / MIM)",
    "Master of Finance (MFin / MiF)",
    "MPhil",
    "Integrated Master of Engineering (MEng)",
    "Integrated Master of Science (MSci / MSc)",
    "BS/MS in Engineering",
    "BS/MS in Computer Science",
    "BS/MS in Data Science / AI",
    "BS/MS in Biotechnology / Life Sciences",
    "BBA + MBA Integrated Programs",
    "BS/BA + Master in Management (MiM)",
    "BA + Master of Public Policy (MPP)",
    "BA + Master of International Relations",
    "BA + Master of Public Administration (MPA)",
    "Integrated Social Sciences Master’s Pathways",
    "BA/MA in Humanities",
    "BA/MA in Languages or Literature",
    "Integrated Liberal Arts Master’s Programs",
    "Integrated Bachelor + Master of Architecture",
    "Integrated Design Master’s Programs",

    # Doctorate
    "Ph.D. (Doctor of Philosophy)",
    "M.D. (Doctor of Medicine)",
]

ALLOWED_TEST_TYPES = [
    "ACT",
    "Executive Assessment",
    "GMAT",
    "GRE",
    "IELTS",
    "SAT",
    "TOEFL",
    "Other",
]

def normalize_test_type(test_type: str) -> tuple[str, str | None]:
    if not test_type or not isinstance(test_type, str):
        return "Other", None
    
    t_clean = test_type.strip()
    
    # Direct match (case-insensitive)
    for t in ALLOWED_TEST_TYPES:
        if t.lower() == t_clean.lower():
            return t, None
            
    # Abbreviation / common mapping
    t_upper = t_clean.upper()
    if t_upper in ["EA", "EXECUTIVE ASSESSMENT"]:
        return "Executive Assessment", None
    if "GMAT" in t_upper:
        return "GMAT", None
    if "GRE" in t_upper:
        return "GRE", None
    if "SAT" in t_upper:
        return "SAT", None
    if "ACT" in t_upper:
        return "ACT", None
    if "TOEFL" in t_upper:
        return "TOEFL", None
    if "IELTS" in t_upper:
        return "IELTS", None
        
    return "Other", t_clean

ALLOWED_LEVELS = [
    "Not Applicable",
    "A Level",
    "AS Level",
    "AP",
    "Advanced",
    "Core",
    "Extended",
    "Higher",
    "Honors",
    "Standard",
]

def normalize_level(level_name: str) -> str:
    if not level_name or not isinstance(level_name, str):
        return "Not Applicable"
        
    lvl_clean = level_name.strip()
    
    # Direct match (case-insensitive)
    for l in ALLOWED_LEVELS:
        if l.lower() == lvl_clean.lower():
            return l
            
    lvl_upper = lvl_clean.upper()
    if "NOT APPLICABLE" in lvl_upper or lvl_upper == "NA" or lvl_upper == "N/A" or lvl_upper == "NONE":
        return "Not Applicable"
    if lvl_upper in ["AS LEVEL", "AS-LEVEL", "AS_LEVEL", "AS"]:
        return "AS Level"
    if lvl_upper in ["A LEVEL", "A-LEVEL", "A_LEVEL", "A"]:
        return "A Level"
    if lvl_upper in ["AP", "ADVANCED PLACEMENT"]:
        return "AP"
    if "ADVANCED" in lvl_upper:
        return "Advanced"
    if "CORE" in lvl_upper:
        return "Core"
    if "EXTENDED" in lvl_upper:
        return "Extended"
    if "HIGHER" in lvl_upper or lvl_upper == "HL":
        return "Higher"
    if "HONOR" in lvl_upper:
        return "Honors"
    if "STANDARD" in lvl_upper or lvl_upper == "SL":
        return "Standard"
        
    return "Not Applicable"

def normalize_grounded_dropdowns(data):
    """
    Recursively scans and updates dropdown values in the parsed payload:
    - 'board' -> normalize_board
    - 'testType' -> normalize_test_type
    - 'level' -> normalize_level
    - 'degree' -> normalize_degree
    """
    if isinstance(data, dict):
        new_data = {k: normalize_grounded_dropdowns(v) for k, v in data.items()}
        
        # 1. Normalize board
        if 'board' in new_data and isinstance(new_data['board'], str):
            normalized, board_other = normalize_board(new_data['board'])
            new_data['board'] = normalized
            if board_other:
                if not new_data.get('boardOther'):
                    new_data['boardOther'] = board_other
                    
        # 2. Normalize testType
        if 'testType' in new_data and isinstance(new_data['testType'], str):
            normalized, test_other = normalize_test_type(new_data['testType'])
            new_data['testType'] = normalized
            if test_other:
                if not new_data.get('testTypeOther'):
                    new_data['testTypeOther'] = test_other
                    
        # 3. Normalize level
        if 'level' in new_data and isinstance(new_data['level'], str):
            new_data['level'] = normalize_level(new_data['level'])
            
        # 4. Normalize degree
        if 'degree' in new_data and isinstance(new_data['degree'], str):
            normalized, degree_other = normalize_degree(new_data['degree'])
            new_data['degree'] = normalized
            if degree_other:
                if not new_data.get('degreeOther'):
                    new_data['degreeOther'] = degree_other
                    
        return new_data
    elif isinstance(data, list):
        return [normalize_grounded_dropdowns(item) for item in data]
    else:
        return data

# Initialize EasyOCR reader once at startup (or lazily) to avoid per-request latency
_EASYOCR_READER = None

def get_easyocr_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr
            # Note: gpu=False for better compatibility in CPU environments
            _EASYOCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception as e:
            print(f"Failed to initialize EasyOCR: {e}")
    return _EASYOCR_READER

class GetProfileView(UserDTOView):
    """
    API to retrieve user profile JSON blob.
    """

    @extend_schema(request=None, responses={200: "Profile JSON with completion metadata."})
    def get(self, request: Request) -> Response:
        target_user_id = self.user_dto.id
        
        success, profile_or_reason = update_user_profile(
            target_user_id, None, retrieve=True
        )

        if success:
            profile_data = profile_or_reason or {}

            # Enrich profile with authoritative User-model fields
            profile_data = enrich_profile_data(target_user_id, profile_data)

            completion_percentage, missing_sections = calculate_profile_completion(profile_data)
            print(f"[Profile GET] Retrieved profile of user {target_user_id}")
            print(f"[Profile GET] Completion: {completion_percentage}%, Missing sections: {missing_sections}")
            return Response({
                "profile": profile_data,
                "completion_percentage": completion_percentage,
                "is_complete": is_profile_complete(profile_data),
                "missing_sections": missing_sections,
            }, status=200)

        print(f"[Profile GET] Error: {profile_or_reason}")
        return Response({"error": profile_or_reason}, status=404)


from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

@method_decorator(csrf_exempt, name='dispatch')
class UpdateProfileView(UserDTOView):
    """
    API to update user profile JSON blob.
    """

    @extend_schema(
        request=None, responses={200: "Profile updated successfully."}
    )
    def post(self, request: Request) -> Response:
        if not isinstance(request.data, dict):
            return Response({"error": "Payload must be a JSON object."}, status=400)

        target_user_id = self.user_dto.id
        print(f"[Profile POST] Updating for user {target_user_id}. Data keys: {list(request.data.keys())}")

        # The frontend usually sends { "profile": { ...data... } }
        # Sometimes it can be double nested due to context updates.
        # Recursively unwrap until we get to the core data.
        new_data = request.data
        while isinstance(new_data, dict) and "profile" in new_data and len(new_data) == 1:
            new_data = new_data["profile"]
            
        if not isinstance(new_data, dict):
            return Response({"error": "Profile data must be a JSON object."}, status=400)

        # Sync firstName/lastName from profile personalDetails to User model
        try:
            personal = new_data.get("personalDetails", {})
            if isinstance(personal, dict):
                first_name = personal.get("firstName", "").strip()
                last_name = personal.get("lastName", "").strip()
                if first_name or last_name:
                    User.objects.filter(id=target_user_id).update(
                        **{k: v for k, v in {"first_name": first_name, "last_name": last_name}.items() if v}
                    )
        except Exception as e:
            print(f"[Profile POST] Failed to sync name: {e}")

        # Sync academicLevel from educational to User.academic_level and strip from profile blob
        import copy
        processed_profile = copy.deepcopy(new_data)
        try:
            educational = processed_profile.get("educational", {})
            if isinstance(educational, dict) and "academicLevel" in educational:
                academic_level_label = educational.pop("academicLevel")
                # Map frontend display labels to backend model choices
                label_to_value = {label: val for val, label in User.AcademicLevel.choices}
                academic_level_val = label_to_value.get(academic_level_label, academic_level_label)
                User.objects.filter(id=target_user_id).update(academic_level=academic_level_val)
                print(f"[Profile POST] Synced academicLevel: {academic_level_val}")
        except Exception as e:
            print(f"[Profile POST] Failed to sync academicLevel: {e}")

        # Always save in the wrapped format { "profile": { ... } } for consistency
        data_to_save = {"profile": processed_profile}
        
        success, reason = update_user_profile(target_user_id, data_to_save)

        if success:
            return Response({"message": "Profile updated successfully."}, status=200)

        return Response({"error": str(reason)}, status=400)


class ResumeParserView(UserDTOView):

    parser_classes = [MultiPartParser]

    def post(self, request):
        # FIX 1: Retrieve uploaded file from request.FILES
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response({"error": "No file provided."}, status=400)

        # FIX 2: Moved file-type handling inside the method with correct indentation
        file_name = uploaded_file.name.lower()

        if file_name.endswith(".pdf"):
            text = pdfminer.high_level.extract_text(uploaded_file.file)

        elif file_name.endswith((".jpg", ".jpeg")):
            # Optimize image for Vision upload
            print(f"Optimizing image for Resume Vision upload: {file_name}")
            img = PILImage.open(uploaded_file).convert('RGB')
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80)
            img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Use Vision logic for resume if image
            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Extract structured student profile data from resume images."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract structured profile data from this resume image. Return JSON with fields: first_name, last_name, email, phone, gender, dob, city, zip_code, citizenship, address, mother_profession, father_profession, institution, degree, major, cgpa, start_year, end_year, current_year, skills, projects, experience, activities, certifications"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}}
                        ]
                    }
                ],
                temperature=0
            )
            try:
                parsed = json.loads(response.choices[0].message.content)
            except:
                parsed = {}
            return Response({"personal": sanitize_years(parsed)})

        else:
            return Response({"error": "File format not supported, pls upload file in pdf/jpg format"}, status=400)

        # FIX 3: Added the missing client.chat.completions.create(...) call and assignment
        response = client.chat.completions.create(
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Extract structured student profile data from resumes."
                },
                {
                    "role": "user",
                    "content": f"""
                    Extract structured profile data from this resume text:         
                    {text}
                    Return JSON with fields:
                        first_name
                        last_name
                        email
                        phone
                        gender
                        dob
                        city
                        zip_code
                        citizenship
                        address
                        mother_profession
                        father_profession
                        institution
                        degree
                        major
                        cgpa
                        start_year (JSON string, extract only the year e.g. "2023")
                        end_year (JSON string, extract only the year e.g. "2024")
                        current_year (JSON string, extract only the year e.g. "2026")
                        skills
                        projects
                        experience
                        activities
                        certifications
                    """  # FIX 4: Closed the f-string properly
                }
            ],
            temperature=0
        )
        import json
        try:
            parsed = json.loads(response.choices[0].message.content)
        except:
            parsed = {}

        return Response({
            "personal": sanitize_years(parsed)
        })

def sanitize_years(data):
    """Recursively sanitize year fields to ensure they only contain YYYY."""
    year_fields = {'yearOfCompletion', 'startYear', 'endYear', 'year', 'start_year', 'end_year', 'current_year'}
    
    if isinstance(data, dict):
        new_data = {}
        for k, v in data.items():
            if k in year_fields and isinstance(v, str) and v:
                # Extract the first 4 digits found in the string
                import re
                match = re.search(r'\b(19|20)\d{2}\b', v)
                if match:
                    new_data[k] = match.group(0)
                else:
                    new_data[k] = v
            else:
                new_data[k] = sanitize_years(v)
        return new_data
    elif isinstance(data, list):
        return [sanitize_years(item) for item in data]
    else:
        return data

class LinkedInParserView(UserDTOView):
    allow_public = False  # Force authentication

    def post(self, request):
        linkedin_text = request.data.get("linkedin_text", "").strip()

        if not linkedin_text:
            return Response({"error": "No profile text provided. Please paste your LinkedIn profile content."}, status=400)

        if len(linkedin_text) < 50:
            return Response({"error": "The pasted content seems too short. Please copy your full LinkedIn profile page (Ctrl+A -> Ctrl+C)."}, status=400)

        print(f"[LinkedInParser] Deep Sync for pasted profile text ({len(linkedin_text)} chars)")

        try:
            # Dropdown constants for the AI to pick from
            EXPERIENCE_TYPES = "['Entrepreneurship', 'Family Business', 'Freelance', 'Full time', 'Internship', 'Part time', 'Project', 'Other']"
            INDUSTRIES = "['Agriculture', 'Aerospace & Defense', 'Arts & Design', 'Automotive', 'Construction & Infrastructure', 'Consulting', 'Data Science', 'Education', 'Energy & Utilities', 'Finance & Banking', 'FMCG / Consumer Goods', 'Government & Public Sector', 'Healthcare & Pharmaceuticals', 'Hospitality & Tourism', 'Insurance', 'Legal', 'Logistics & Supply Chain', 'Manufacturing', 'Media & Entertainment', 'Non-Profit & NGO', 'Real Estate', 'Research & Development', 'Retail & E-commerce', 'Sports & Fitness', 'Technology & IT', 'Telecommunications', 'Other']"
            ACADEMIC_LEVELS = "['College/Undergraduate', 'High School (8th–12th grade)', 'Postgraduate', 'Working/Completed College']"
            PROFICIENCIES = "['Native', 'Advanced', 'Intermediate', 'Basic']"

            # 100% Correct Frontend Schema
            json_template = """{
  "personalDetails": {
    "firstName": "", "lastName": "", "email": "", "phoneNumber": "", "dob": "", "gender": "", "citizenShip": "India", "city": "",
    "languages": [
      {"language": "", "proficiency": "Native", "type": ["Read", "Write", "Speak"], "comment": ""}
    ]
  },
  "educational": [
    {
      "academicLevel": "High School (8th–12th grade)", 
      "gradeLevel": "Grade 10",
      "schoolName": "",
      "city": "",
      "board": "CBSE",
      "yearOfCompletion": "",
      "overallPercentage": "",
      "institutionName": "", 
      "degree": "", 
      "major": "", 
      "startYear": "", 
      "endYear": ""
    }
  ],
  "awards": [
    {"nameOfHonorReceived": "", "description": "", "levelOfCompetitiveness": "National", "year": ""}
  ],
  "courses": [
    {"courseType": "Academic", "description": "", "year": "", "duration": ""}
  ],
  "professional": {
    "experiences": [
      {
        "experienceType": "Internship", 
        "industrySector": "Technology & IT",
        "currentEmployer": "", 
        "jobTitle": "", 
        "city": "",
        "startDate": "", 
        "endDate": "", 
        "responsibilities": "", 
        "achievements": ""
      }
    ]
  },
  "extraCurricular": [
    {
      "activityType": "Volunteer Work", 
      "positionHeld": "", 
      "startDate": "", 
      "endDate": "", 
      "description": "", 
      "awardsCertifications": ""
    }
  ]
}"""

            prompt = (
                "You are an ELITE LinkedIn profile data miner. Your goal is 100% data extraction accuracy for EVERY academic stage.\n"
                "RAW CONTENT:\n" + linkedin_text[:18000] + "\n\n"
                "MISSION: Extract ALL education records, awards, and courses.\n"
                "STRICT ROUTING RULES:\n"
                "1. ANY Course/Certification/Bootcamp (e.g., 'Graph Theory Programming Camp', 'Certificate of Completion', 'Python Specialist'): PUT THESE ONLY IN THE 'courses' ARRAY.\n"
                "2. ANY Academic Honor/Rank/Scholarship (e.g., 'Gold Medalist', 'Top 1%'): PUT THESE ONLY IN THE 'awards' ARRAY.\n"
                "3. EXTRA-CURRICULAR: Use ONLY for Volunteer work, Student Organizations, Sports, or Leadership roles. DO NOT put academic certificates here.\n"
                "4. educational: MUST be an array. Include separate objects for each degree (10th, 12th, UG, PG).\n"
                "5. Mapping Academic Levels: Use ONLY " + ACADEMIC_LEVELS + ".\n"
                "6. Mapping Skills/Scores: Map test scores (CBSE) to the overallPercentage of the matching school entry.\n\n"
                "TARGET JSON STRUCTURE:\n" + json_template
            )

            ai_response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a specialized profile data extractor. You capture every detail and return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )

            content = ai_response.choices[0].message.content
            parsed = json.loads(content)

            # Standard profile data sanitization
            parsed = sanitize_years(parsed)
            parsed = normalize_grounded_dropdowns(parsed)

            return Response(parsed)

        except Exception as e:
            import traceback
            print(f"[LinkedInParser] AI Parsing error:\n{traceback.format_exc()}")
            return Response({"error": f"Deep Scan failed: {str(e)}"}, status=500)






class TranscriptParserView(UserDTOView):
    parser_classes = [MultiPartParser]
    allow_public = False # Force authentication

    def dispatch(self, request, *args, **kwargs):
        print(f"[TranscriptParser] Dispatching {request.method} {request.path}")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        print(f"[TranscriptParser] Received request. Files: {request.FILES.keys()}")
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response({"error": "No file provided."}, status=400)

        file_name = uploaded_file.name.lower()
        text = ""
        images_base64 = [] # For Vision API

        try:
            file_content = uploaded_file.read()
            if file_name.endswith(".pdf"):
                # Extract text for maximum speed and accuracy
                print(f"Processing PDF for text extraction...")
                doc = fitz.open(stream=file_content, filetype="pdf")
                pdf_text_parts = []
                for page_num in range(min(len(doc), 10)):
                    page = doc.load_page(page_num)
                    pdf_text_parts.append(page.get_text())
                
                text = "\n".join(pdf_text_parts)
                
                # Only use images / Vision OCR if the PDF has very little selectable text (e.g., scanned PDF)
                if len(text.strip()) < 200:
                    print(f"PDF contains minimal selectable text ({len(text)} chars). Extracting high-res page images for Vision OCR...")
                    for page_num in range(min(len(doc), 10)):
                        page = doc.load_page(page_num)
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        img_bytes = pix.tobytes("jpg", jpg_quality=85)
                        images_base64.append(base64.b64encode(img_bytes).decode('utf-8'))
                else:
                    print(f"PDF contains ample selectable text ({len(text)} chars). Skipping image/Vision overhead to avoid model context crowding.")
                
                print(f"PDF processing done: {len(text)} chars, {len(images_base64)} images")

            elif file_name.endswith(".docx"):
                try:
                    print(f"Attempting to extract text from DOCX: {file_name}")
                    text = extract_docx(io.BytesIO(file_content))
                    print(f"DOCX extraction success: {len(text)} chars")
                except Exception as docx_err:
                    print(f"DOCX extraction failed: {str(docx_err)}")
                    text = ""

            elif file_name.endswith(".doc"):
                # .doc files are binary OLE files. python-docx cannot read them.
                # We do a basic string extraction of printable characters as a fallback.
                print(f"Attempting legacy DOC extraction: {file_name}")
                try:
                    # Extract printable characters only to avoid messing up AI/Terminal
                    raw_text = file_content.decode('latin-1', errors='ignore')
                    text = "".join([c for c in raw_text if c.isprintable() or c in "\n\r\t"])
                    print(f"Legacy DOC extraction success: {len(text)} chars")
                except:
                    text = ""

            elif file_name.endswith((".jpg", ".jpeg")):
                print(f"Optimizing image for Vision upload: {file_name}")
                # Re-encode image to JPEG 80 if it's too large or not JPEG
                img = PILImage.open(io.BytesIO(file_content)).convert('RGB')
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=80)
                images_base64.append(base64.b64encode(buffer.getvalue()).decode('utf-8'))

            else:
                return Response({"error": "File format not supported, pls upload file in pdf/jpg format"}, status=400)

        except Exception as e:
            import traceback
            print(f"File processing error: {traceback.format_exc()}")
            return Response({"error": f"Error processing file: {str(e)}"}, status=400)

        if not text and not images_base64:
            return Response({"error": "Could not extract any content from the document."}, status=400)

        # print(f"Extracted Text Preview: {text[:500]}...") # Removed to avoid UnicodeEncodeError on Windows terminal
        print(f"Sending {len(text)} chars to {settings.AZURE_OPENAI_DEPLOYMENT}...")

        prompt = f"""Extract all student profile data from this document (transcript or resume).
Return ONLY a valid JSON object with the exact structure below. 

STRICT RULES:
1. CRITICAL EXTRACTION DIRECTIVE: Do NOT skip, omit, summarize, or truncate ANY items. You MUST extract every single educational experience, school term, grade/score, subject, professional internship, full-time job, project, extra-curricular activity, certification, course, and award in its entirety. Full exhaustiveness is mandatory.
2. DO NOT HALLUCINATE. If a piece of information is not present, return an empty string "" or an empty array [].
2. PERSONAL DETAILS: 
   - countryCode: Extract the numeric country code prefix (e.g. "+91" or "91").
   - phoneNumber: Extract ONLY the mobile number without the country code.
   - dob: Look for "DOB" or "Date of Birth". (e.g. "22 March 2003" -> "2003-03-22").
   - gender: "Male", "Female", or "Other".
   - citizenShip: Extract nationality/citizenship (e.g. "Indian").
   - addressline: Extract the street address/house number.
   - city: Extract the city name.
   - zipcode: Extract the 6-digit pin code or zip code.
3. INSTITUTION NAME: Look for the specific college name. 
4. DATES vs YEARS: 
    - For FULL DATES (dob, testDate, startDate, endDate): Use YYYY-MM-DD format. If a date says "Present" or "Current", use "2026-05-09".
    - For YEARS ONLY (yearOfCompletion, startYear, endYear, year): Use exactly 4 digits (e.g. "2024"). DO NOT include month or day.
5. ACADEMIC LEVEL: Use exactly one of: "High School (8th–12th grade)", "College/Undergraduate", "Postgraduate", "Working Professional". 
   - CRITICAL: If the document contains any Full-time professional work experience (excluding internships), the ACADEMIC LEVEL must be "Working Professional".
   - If the person has completed a Bachelor's degree and is currently in a Master's or has professional experience, it must NOT be "College/Undergraduate".
6. EDUCATIONAL RECORDS: Extract ALL educational experiences (High School, Bachelor, Master, etc.) into the "educational" array. Ground the `degree` field to the standard degrees if possible (e.g. "B.A. (Bachelor of Arts)", "B.E. (Bachelor of Engineering)", "B.T. (Bachelor of Technology)", "B.Sc (Bachelor of Science)", "B.Com (Bachelor of Commerce)", "B.B.A. (Bachelor of Business Administration)", "M.B.A. (Master of Business Administration)", "M.Sc (Master of Science)", "M.Tech (Master of Technology)", "Ph.D. (Doctor of Philosophy)", etc.). If the degree is not standard, return "Other" and set the original degree name in `degreeOther`.
7. PROFESSIONAL EXPERIENCES: Extract all work experiences into the "professional.experiences" array.
8. HIGH SCHOOL DATA: For each High School record:
   - Set `academicLevel` to exactly "High School (8th–12th grade)".
   - Set `gradeLevel` to the NUMERIC grade only (e.g. 12 for "12th grade" or "Grade 12", 10 for "10th grade"). Do NOT include any text suffix.
   - Extract `board`. Ground/map this strictly to the board type dropdown options. Output EXACTLY one of:
     * "American (AP / US High School Diploma)"
     * "Cambridge - A Levels"
     * "Cambridge - IGCSE"
     * "CBSE"
     * "HSC"
     * "IBCP" (use this if the transcript states IBCP or Career-related Programme)
     * "ICSE"
     * "International Baccalaureate (IB)" (e.g. if the transcript says "IB" or "International Baccalaureate" or "IBDP")
     * "ISC"
     * "MYP" (use this if the transcript states MYP or Middle Years Programme)
     * "NIOS"
     * "State Board" (use this for all state boards, e.g. MSBSHSE, Maharashtra Board, etc.)
     * "Other"
     If you map it to "Other", fill in the original board name in the `boardOther` field.
   - Extract `overallPercentage` as the overall/aggregate percentage or score (a plain number, NO % symbol). If per-subject scores are given and no aggregate is stated, leave it empty.
   - Extract all `subjects` with their scores.
   - TERM/SEMESTER-WISE DATA FOR HIGH SCHOOL: If the transcript has term-wise or semester-wise subject breakdowns, extract them into the `terms` array. Each entry should have `termName` (e.g. "Term 1", "Semester 1") and a `subjects` array with the same structure as the top-level subjects.
9. SUBJECTS: For each subject, extract the name, level, marks obtained (yourTotalScore as a plain number, NO % symbol), and maximum possible marks (highestTotalScore, also a plain number e.g. 100). Ground the `level` field strictly to one of: "Not Applicable", "A Level", "AS Level", "AP", "Advanced", "Core", "Extended", "Higher", "Honors", "Standard".
10. SCORES & PERCENTILES: Always return numeric scores and percentiles as plain integers or numbers WITHOUT any suffix, symbol, or unit. Do NOT include "%", "th", "rd", "st", "CGPA", "GPA", "/100", etc. Just the number (e.g. "97th Percentile" -> 97, "95%" -> 95, "7.8 CGPA" -> 7.8).
11. PROFESSIONAL EXPERIENCES: 
   - experienceType: Use "Internship", "Full-time", or "Project".
   - currentEmployer: Company name.
   - city: City of the workplace.
   - responsibilities: Bullet points or summary of what was done.
   - achievements: Key results or metrics achieved.
   - startDate/endDate: Extract the month and year (e.g. "May 2023" -> "2023-05-01"). If endDate is "Present", use "2026-05-09".
12. COURSES & CERTIFICATIONS: Extract ALL academic or professional certifications (e.g. Coursera, AWS, NPTEL, Online Courses). Map these to the "courses" array.
13. AWARDS & SCHOLARSHIPS: Extract ALL academic honors, dean's list, scholarships, competition wins (e.g. GSoC, Hackathons, Rank in exams). Map these to the "awards" array.
    - IMPORTANT: Extract these regardless of whether they belong to High School, UG, or PG. They should all go into these global arrays.
    - Note: These items are often found in sections like "ACHIEVEMENTS", "AWARDS", "FELLOWSHIPS", or "CERTIFICATIONS".
14. TEST SCORES: Extract ALL standardized test scores (SAT, ACT, GRE, GMAT, TOEFL, IELTS, Executive Assessment, AP, etc.). Ground the `testType` field strictly to one of: "ACT", "Executive Assessment", "GMAT", "GRE", "IELTS", "SAT", "TOEFL", "Other". If you choose "Other", specify the original test name in the `testTypeOther` field.
    - ALWAYS extract percentiles if given! Even if they are inside yellow boxes or tables (e.g. "97th Percentile", "96th", "93rd"). Clean them to plain numbers (e.g. 97, 96, 93).
    - For GMAT / GMAT Focus: Extract totalScore, yourPercentile (overall percentile e.g. 96), dataInsightsScore, dataInsightsPercentile (e.g. 90), verbalReasoningScore, verbalReasoningPercentile (e.g. 93), quantitativeReasoningScore, quantitativeReasoningPercentile (e.g. 97).
    - For GRE: Extract totalScore, analyticalWritingScore, analyticalWritingPercentile (e.g. 93), verbalReasoningScore, verbalReasoningPercentile (e.g. 91), quantitativeReasoningScore, quantitativeReasoningPercentile (e.g. 96).
    - For SAT: Extract totalScore, mathYourScore, mathYourPercentile, criticalReadingYourScore (which represents the combined Evidence-Based Reading and Writing score), criticalReadingYourPercentile.
    - For ACT: Extract totalScore, englishYourScore, englishYourPercentile, mathYourScore, mathYourPercentile, readingYourScore, readingYourPercentile, scienceYourScore, scienceYourPercentile.
    - For Executive Assessment: Extract totalScore, integratedReasoningScore, integratedReasoningPercentile, verbalReasoningScore, verbalReasoningPercentile, quantitativeReasoningScore, quantitativeReasoningPercentile.
    - For TOEFL & IELTS: Extract totalScore. Also extract subject-wise scores if available: readingYourScore, listeningYourScore, speakingYourScore, writingYourScore.
    - For AP (Advanced Placement): Extract as testType "AP". Extract the subject name into `testType` (e.g. "AP Physics") and the score (1-5) into `yourScore`.
    - For Others: Extract yourScore.
15. SKILLS & PROJECTS: Extract skills and major projects. Map these to "additional" section if no specific section exists.

UNIVERSITY SEMESTER/YEAR-WISE SCORES (CRITICAL - DO NOT SKIP):
- For any College/Undergraduate, Postgraduate, or Working Professional record, if the transcript contains semester-wise or year-wise GPA/SGPA/scores, you MUST extract them.
- SET `hasSemesterWiseScores`: 
  * "Yes" if the items are Semesters (usually 2 per year, e.g., 1st to 8th Semester for a 4-year degree).
  * "No" if the items are Years (usually 1 per year, e.g., 1st to 4th Year for a 4-year degree).
- SEMESTER COUNT LOGIC:
  * For a standard 4-year Bachelor's degree (B.E., B.Tech, B.A., B.Sc, B.Com), expect 8 Semesters or 4 Years.
  * For a standard 2-year Master's degree, expect 4 Semesters or 2 Years.
  * CRITICAL: IF you extract 8 items for a Bachelor's degree, it is 100% a SEMESTER-WISE breakdown; you MUST set `hasSemesterWiseScores` to "Yes".
  * IF you extract 6 items for a 3-year Bachelor's degree, it is 100% a SEMESTER-WISE breakdown; set `hasSemesterWiseScores` to "Yes".
- Extract each semester or year as an object in the `semesters` array with fields `semesterName`, `score`, and `highestTotalScore`.
- Each semester object: {{ "semesterName": "Monsoon 2023", "score": 3.53, "highestTotalScore": 4.0 }}. 
- USE SEMESTER NAMES: Look for and capture term names like "Monsoon", "Autumn", "Spring", "Winter", "Summer", "Fall" along with the year (e.g. "Spring 2024"). 
- If the transcript uses "1st Semester", "Sem 1", etc., use those.
- Accuracy for GPA: Extract SGPA, GPA, or Term GPA exactly as found. If the transcript shows "GPA: 3.53", set `score` to 3.53.
- DO NOT mix semester names with year-wise data. If you have 8 items, they MUST be labeled as Semesters, and `hasSemesterWiseScores` MUST be "Yes".
- This is MANDATORY. If 8 semesters are in the transcript, the `semesters` array must have 8 entries (though the UI may cap the initial display).

100% ACCURACY FOR DEGREE DETAILS:
- institutionName: Extract full legal university/college name.
- degree: Extract exact degree (e.g. "Bachelor of Technology", "Master of Business Administration").
- major: Extract exact specialization (e.g. "Mechanical Engineering", "Finance").
- startYear / endYear: Extract exact years of study.
- overallPercentage / maximumPossibleGPA: Extract the final cumulative score if available.

JSON STRUCTURE:
{{
  "personalDetails": {{ "firstName": "", "lastName": "", "email": "", "countryCode": "", "phoneNumber": "", "dob": "YYYY-MM-DD", "gender": "", "citizenShip": "", "addressline": "", "city": "", "zipcode": "", "mothersProfession": "", "fathersProfession": "" }},
  "educational": [
    {{
       "academicLevel": "High School (8th\u201312th grade)", "gradeLevel": 12, "institutionName": "", "city": "", "yearOfCompletion": "YYYY",
       "overallPercentage": "", "maximumPossibleGPA": "",
       "degree": "", "degreeOther": "", "major": "", "startYear": "YYYY", "endYear": "YYYY",
       "board": "",
       "boardOther": "",
       "subjects": [
          {{ "subject": "", "level": "", "yourTotalScore": "", "highestTotalScore": "100" }}
       ],
       "terms": [
          {{ "termName": "Term 1", "subjects": [{{ "subject": "", "level": "", "yourTotalScore": "", "highestTotalScore": "100" }}] }}
       ],
       "hasSemesterWiseScores": "Yes",
       "semesters": [
          {{ "semesterName": "1st Semester", "sgpa": 0.0, "maxSgpa": 10.0 }}
       ]
    }}
  ],
  "courses": [
     {{ "courseType": "", "description": "", "year": "YYYY", "awards": "", "duration": "", "location": "" }}
  ],
  "awards": [
     {{ "nameOfHonorReceived": "", "description": "", "levelOfCompetitiveness": "", "numberOfParticipants": "", "year": "YYYY" }}
  ],
  "testScores": [ 
    {{ 
      "testType": "", "testTypeOther": "", "testDate": "YYYY-MM-DD", "totalScore": "", "yourScore": "", "yourPercentile": "",
      "mathYourScore": "", "mathYourPercentile": "", "criticalReadingYourScore": "", "criticalReadingYourPercentile": "",
      "analyticalWritingScore": "", "analyticalWritingPercentile": "", "verbalReasoningScore": "", "verbalReasoningPercentile": "", "quantitativeReasoningScore": "", "quantitativeReasoningPercentile": "",
      "dataInsightsScore": "", "dataInsightsPercentile": "", "englishYourScore": "", "englishYourPercentile": "", "readingYourScore": "", "readingYourPercentile": "", "scienceYourScore": "", "scienceYourPercentile": "",
      "integratedReasoningScore": "", "integratedReasoningPercentile": "", "listeningYourScore": "", "listeningYourPercentile": "", "speakingYourScore": "", "speakingYourPercentile": "", "writingYourScore": "", "writingYourPercentile": ""
    }} 
  ],
  "professional": {{
     "experiences": [ 
        {{ "experienceType": "", "currentEmployer": "", "startDate": "YYYY-MM-DD", "endDate": "YYYY-MM-DD", "jobTitle": "", "city": "", "industrySector": "", "responsibilities": "", "achievements": "" }} 
     ]
  }},
  "extraCurricular": [
     {{ "activityType": "", "startDate": "YYYY-MM-DD", "endDate": "YYYY-MM-DD", "positionHeld": "", "awardsCertifications": "", "description": "" }}
  ],
  "skills": [],
  "projects": [ {{ "title": "", "description": "", "startDate": "", "endDate": "" }} ]
}}

Document content:
{text[:100000]}
"""

        try:
            messages = [
                {"role": "system", "content": "You are an expert academic data extractor. Extract data from the provided text and images, and return valid JSON only."}
            ]
            
            if images_base64:
                user_content = [
                    {"type": "text", "text": prompt},
                ]
                for img in images_base64:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img}", "detail": "high"}
                    })
                messages.append({"role": "user", "content": user_content})
            else:
                messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT,
                response_format={"type": "json_object"},
                messages=messages,
                temperature=0
            )
            print("Azure OpenAI response received.")
            content = response.choices[0].message.content
            # print(f"--- AI RESPONSE START ---\n{content}\n--- AI RESPONSE END ---")
            
            # Save raw AI response to a local file for debugging
            try:
                scratch_dir = os.path.join(settings.BASE_DIR, 'scratch')
                os.makedirs(scratch_dir, exist_ok=True)
                with open(os.path.join(scratch_dir, 'last_ai_response.json'), 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Saved raw AI response to local scratch file.")
            except Exception as save_err:
                print(f"Failed to save AI response to scratch: {save_err}")
                
            parsed = json.loads(content)
            # Sanitize years and ground dropdown options before returning
            parsed = sanitize_years(parsed)
            parsed = normalize_grounded_dropdowns(parsed)
            print(f"Successfully parsed AI response with keys: {list(parsed.keys())}")
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Azure OpenAI error: {error_trace}")
            return Response({
                "error": f"AI processing failed: {str(e)}",
                "trace": error_trace if settings.DEBUG else None
            }, status=500)

        return Response(parsed)