from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from .dtos import UserDTO
from .roles import UserRole


class RolePermission(BasePermission):
    """
    Custom permission to allow access based on roles.
    """

    def __init__(self, allow_public: bool | None = None):
        self.allow_public = allow_public or False

    def has_permission(self, request: Request, view) -> bool:  # type: ignore

        allow_public = getattr(view, "allow_public", self.allow_public)

        if allow_public:
            return True

        if not isinstance(request.user, UserDTO):
            raise PermissionDenied(detail="Access denied")

        user: UserDTO = request.user
        if not user:
            raise PermissionDenied(detail="Access denied")

        return True


def _get_user_dto(request: Request) -> UserDTO:
    if not isinstance(request.user, UserDTO):
        raise PermissionDenied(detail="Access denied")
    return request.user


class IsSuperAdmin(BasePermission):
    def has_permission(self, request: Request, view) -> bool:  # type: ignore
        user = _get_user_dto(request)
        if user.role != UserRole.SUPERADMIN:
            raise PermissionDenied(detail="Superadmin access required")
        return True


class IsSuperOrOperationAdmin(BasePermission):
    def has_permission(self, request: Request, view) -> bool:  # type: ignore
        user = _get_user_dto(request)
        if user.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")
        return True


class IsSchoolAdmin(BasePermission):
    def has_permission(self, request: Request, view) -> bool:  # type: ignore
        user = _get_user_dto(request)
        if user.role != UserRole.SCHOOLADMIN:
            raise PermissionDenied(detail="School admin access required")
        return True


class IsAnyAdmin(BasePermission):
    def has_permission(self, request: Request, view) -> bool:  # type: ignore
        user = _get_user_dto(request)
        if user.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN):
            raise PermissionDenied(detail="Admin access required")
        return True


class SchoolScopedPermission(BasePermission):
    """Ensures schooladmins can only access their own school's resources."""

    def has_permission(self, request: Request, view) -> bool:  # type: ignore
        user = _get_user_dto(request)
        if user.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return True
        if user.role == UserRole.SCHOOLADMIN:
            school_id = view.kwargs.get("school_id")
            if school_id and user.school_id != int(school_id):
                raise PermissionDenied(detail="Access denied to this school")
            return True
        raise PermissionDenied(detail="Admin access required")
