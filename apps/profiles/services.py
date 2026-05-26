import logging

from .models import UserProfile

logger = logging.getLogger(__name__)

# Required fields in each profile section used to compute completion percentage.
# These mirror the fields marked `required: true` in the frontend fieldDefinitions.
_PERSONAL_REQUIRED_FIELDS = [
    "dob", "countryCode", "phoneNumber",
    "gender", "addressline", "city", "zipcode", "citizenShip", "annualIncome",
]
_EDUCATIONAL_REQUIRED_FIELDS = ["academicLevel"]
_ADDITIONAL_REQUIRED_FIELDS = ["degreeInterest", "domainInterest"]

# Dict-based sections: each entry is checked field-by-field
_DICT_SECTIONS: list[tuple[str, list[str]]] = [
    ("personalDetails", _PERSONAL_REQUIRED_FIELDS),
    ("educational", _EDUCATIONAL_REQUIRED_FIELDS),
]

# Array-based sections: considered filled if the list has at least one entry
_ARRAY_SECTIONS: list[str] = []

# All section keys (used for the default missing list)
_ALL_SECTION_KEYS = [s for s, _ in _DICT_SECTIONS] + _ARRAY_SECTIONS


def _is_value_filled(val: object) -> bool:
    """Return True when *val* contains meaningful data."""
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip() != ""
    if isinstance(val, (list, dict)):
        return len(val) > 0
    return True


def calculate_profile_completion(profile_json: dict) -> tuple[int, list[str]]:
    """
    Calculate what percentage of required profile fields are filled in.
    Each section contributes as requested:
    - Personal Details: 22.5%
    - Educational: 22.5%
    - Professional: 22.5%
    - Extra-curricular (extraCurricular): 22.5%
    - Additional: 10%
    """
    if not isinstance(profile_json, dict):
        return 0, ["personalDetails", "educational", "professional", "extraCurricular", "additional"]

    inner = profile_json.get("profile", profile_json)
    if not isinstance(inner, dict):
        return 0, ["personalDetails", "educational", "professional", "extraCurricular", "additional"]

    missing_sections: list[str] = []
    total_percentage = 0.0

    # 1. Personal Details (22.5%)
    personal_data = inner.get("personalDetails", {})
    if isinstance(personal_data, dict) and personal_data:
        filled = sum(1 for f in _PERSONAL_REQUIRED_FIELDS if _is_value_filled(personal_data.get(f)))
        total_percentage += (filled / len(_PERSONAL_REQUIRED_FIELDS)) * 22.5
        if filled < len(_PERSONAL_REQUIRED_FIELDS):
            missing_sections.append("personalDetails")
    else:
        missing_sections.append("personalDetails")

    # 2. Educational (22.5%)
    educational_data = inner.get("educational", {})
    if isinstance(educational_data, dict) and educational_data:
        filled = sum(1 for f in _EDUCATIONAL_REQUIRED_FIELDS if _is_value_filled(educational_data.get(f)))
        total_percentage += (filled / len(_EDUCATIONAL_REQUIRED_FIELDS)) * 22.5
        if filled < len(_EDUCATIONAL_REQUIRED_FIELDS):
            missing_sections.append("educational")
    else:
        missing_sections.append("educational")

    # 3. Professional (22.5%) - Non-empty experiences array
    professional_data = inner.get("professional", {})
    if isinstance(professional_data, dict) and professional_data:
        experiences = professional_data.get("experiences", [])
        if isinstance(experiences, list) and len(experiences) > 0:
            total_percentage += 22.5
        else:
            missing_sections.append("professional")
    else:
        missing_sections.append("professional")

    # 4. Extra-curricular (22.5%) - Non-empty array counts as 22.5%
    extra_curricular = inner.get("extraCurricular", [])
    if isinstance(extra_curricular, list) and len(extra_curricular) > 0:
        total_percentage += 22.5
    else:
        missing_sections.append("extraCurricular")

    # 5. Additional (10%)
    additional_data = inner.get("additional", {})
    if isinstance(additional_data, dict) and additional_data:
        filled = sum(1 for f in _ADDITIONAL_REQUIRED_FIELDS if _is_value_filled(additional_data.get(f)))
        total_percentage += (filled / len(_ADDITIONAL_REQUIRED_FIELDS)) * 10
        if filled < len(_ADDITIONAL_REQUIRED_FIELDS):
            missing_sections.append("additional")
    else:
        missing_sections.append("additional")

    return int(min(total_percentage, 100)), missing_sections


# def is_profile_complete(profile_json: dict) -> bool:
#     """Returns True when the profile has all required fields filled."""
#     percentage, _ = calculate_profile_completion(profile_json)
#     return percentage == 100


def is_profile_complete(profile_json: dict) -> bool:
    percentage, missing_sections = calculate_profile_completion(profile_json)

    profile_inner = profile_json.get("profile", {})

    personal = profile_inner.get("personalDetails", {})
    educational = profile_inner.get("educational", {})

    personal_completed = isinstance(personal, dict) and len(personal) > 0
    educational_completed = isinstance(educational, dict) and len(educational) > 0

    return (
        percentage >= 60
        and personal_completed
        and educational_completed
    )


def enrich_profile_data(user_id: int, profile_data: dict) -> dict:
    """
    Overlay authoritative fields from the User model onto the profile blob.

    Currently enriches:
      - personalDetails.firstName / lastName
      - educational.academicLevel

    This must be called after retrieving the raw profile blob and before
    computing completion or passing the data to any consumer so that every
    caller sees consistent values.
    """
    from apps.accounts.models import User  # local import to avoid circular deps

    try:
        user = (
            User.objects
            .filter(id=user_id)
            .values("first_name", "last_name", "academic_level")
            .first()
        )
        if not user:
            return profile_data
    except Exception as exc:
        logger.warning("enrich_profile_data: failed to load User %s – %s", user_id, exc)
        return profile_data

    has_profile_key = "profile" in profile_data
    profile_inner = profile_data["profile"] if has_profile_key else profile_data
    if not isinstance(profile_inner, dict):
        return profile_data

    # --- personalDetails: firstName / lastName ---
    first_name = (user.get("first_name") or "").strip()
    last_name = (user.get("last_name") or "").strip()
    if first_name or last_name:
        personal = profile_inner.get("personalDetails", {})
        if not isinstance(personal, dict):
            personal = {}
        if first_name:
            personal["firstName"] = first_name
        if last_name:
            personal["lastName"] = last_name
        profile_inner["personalDetails"] = personal

    # --- educational: academicLevel ---
    raw_level = user.get("academic_level")
    if raw_level:
        educational = profile_inner.get("educational", {})
        if not isinstance(educational, dict):
            educational = {}
        display_map = dict(User.AcademicLevel.choices)
        educational["academicLevel"] = display_map.get(raw_level, raw_level)
        profile_inner["educational"] = educational

    if has_profile_key:
        profile_data["profile"] = profile_inner
    return profile_data


def update_user_profile(
    user_id: int, profile_data: object | None = None, retrieve: bool = False
) -> tuple[bool, object | str | None]:
    """
    Stores or retrieves user profile JSON blob.
    """
    # Validate user_id
    if not user_id or not isinstance(user_id, int) or user_id <= 0:
        print(f"[SERVICES] Invalid user_id: {user_id}")
        return False, "Invalid user ID"
    
    try:
        obj, created = UserProfile.objects.get_or_create(user_id=user_id)
        if created:
            print(f"[SERVICES] Created NEW profile for user_id: {user_id}")
        else:
            print(f"[SERVICES] Retrieved existing profile for user_id: {user_id}")

        if retrieve:
            profile_data_to_return = obj.profile_json if obj.profile_json else {}
            print(f"[SERVICES] Returning profile data. Has data: {bool(obj.profile_json)}, Keys: {list(profile_data_to_return.keys()) if isinstance(profile_data_to_return, dict) else 'N/A'}")
            return True, profile_data_to_return
        if not isinstance(profile_data, object):
            return False, "Profile data must be a JSON object."
        obj.profile_json = profile_data
        obj.save()
        print(f"[SERVICES] Saved profile data for user_id: {user_id}")
        return True, None
    except Exception as e:
        print(f"[SERVICES] Error: {str(e)}")
        return False, str(e)
