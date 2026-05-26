"""
User-related utility functions to avoid duplication across views
"""
from apps.accounts.models import User


def get_user_instance(request_user):
    """
    Get actual User model instance from request.user (which may be a UserDTO).
    
    Args:
        request_user: The user object from request.user
        
    Returns:
        User instance or None if user is anonymous or doesn't exist
    """
    if hasattr(request_user, 'is_anonymous') and request_user.is_anonymous:
        return None
    # request.user is a UserDTO, get the actual User model instance
    try:
        return User.objects.get(id=request_user.id)
    except User.DoesNotExist:
        return None


def get_user_display_name(user_profile_data: dict = None, user=None, fallback: str = 'Student') -> str:
    """
    Extract user's display name from User model.
    
    Args:
        user_profile_data: Unused, kept for backward compatibility.
        user: User model instance
        fallback: Fallback name if no name found
        
    Returns:
        User's display name or fallback
    """
    if user:
        if hasattr(user, 'first_name') and user.first_name:
            return user.first_name
        if hasattr(user, 'email') and user.email:
            return user.email.split('@')[0] or fallback

    return fallback
