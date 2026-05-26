"""
Profile service utilities to avoid duplication across discovery services
"""
import copy
from typing import Dict, Any, Optional
from apps.profiles.models import UserProfile


def get_user_profile_data(user) -> Dict[str, Any]:
    """
    Get the user's profile data for AI context.

    Injects ``academic_level`` from the User model (source of truth) into
    ``profile.educational.academicLevel`` so that all downstream consumers
    see the correct value without querying the User table themselves.
    
    Args:
        user: User model instance
        
    Returns:
        dict: User profile JSON data or empty dict if not found
    """
    if not user:
        return {}
    # Safely get user id
    user_id = getattr(user, 'id', None)
    if not user_id:
        return {}
    try:
        profile = UserProfile.objects.filter(user_id=user_id).first()
        if profile and profile.profile_json:
            data = copy.deepcopy(profile.profile_json)
        else:
            data = {}

        # Inject authoritative fields from User model (source of truth)
        profile_inner = data.get("profile", data)
        if isinstance(profile_inner, dict):
            # firstName / lastName
            first_name = (getattr(user, 'first_name', '') or '').strip()
            last_name = (getattr(user, 'last_name', '') or '').strip()
            if first_name or last_name:
                personal = profile_inner.get("personalDetails", {})
                if not isinstance(personal, dict):
                    personal = {}
                if first_name:
                    personal["firstName"] = first_name
                if last_name:
                    personal["lastName"] = last_name
                profile_inner["personalDetails"] = personal

            # academicLevel
            academic_level = getattr(user, 'academic_level', None)
            if academic_level:
                educational = profile_inner.get("educational", {})
                if not isinstance(educational, dict):
                    educational = {}
                from apps.accounts.models import User
                display_map = dict(User.AcademicLevel.choices)
                educational["academicLevel"] = display_map.get(academic_level, academic_level)
                profile_inner["educational"] = educational

            if "profile" in data:
                data["profile"] = profile_inner

        return data
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return {}
