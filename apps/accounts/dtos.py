from dataclasses import dataclass
from .roles import UserRole


@dataclass
class UserDTO:
    id: int
    email: str
    is_active: bool
    role: str = UserRole.STUDENT
    first_name: str = ""
    last_name: str = ""
    school_id: int | None = None
    school_name: str | None = None
    terms_accepted: bool = False
    force_password_change: bool = False
    
    @property
    def is_authenticated(self) -> bool:
        """
        Always return True for authenticated users.
        This property is required by Django REST Framework permissions.
        """
        return True
