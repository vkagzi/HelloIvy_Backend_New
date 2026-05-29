import logging
from utils.email import send_otp_email
from .dtos import UserDTO
from .models import EmailOTP, User

logger = logging.getLogger(__name__)


class AccountsService:
    @staticmethod
    def create_user(email: str) -> tuple[bool, str]:
        # try creating a new user
        try:
            existing_user = User.objects.filter(email=email).first()
            if existing_user:
                user = existing_user
                if user.password is not None and len(user.password) > 0:
                    return False, "User already exists"
            else:
                user = User(email=email, is_active=False)
                user.save()
            
            # Deactivate any existing active OTPs for this email
            EmailOTP.objects.filter(email=email, is_active=True).update(is_active=False)
            
            # Create new OTP
            otp = EmailOTP(email=email, code=EmailOTP.generate_otp())
            otp.save()
            try:
                send_otp_email(email, str(otp.code))
            except Exception as email_err:
                logger.warning(f"OTP email failed — check terminal for OTP code: {email_err}")

            return True, "User created successfully"
        except Exception as e:
            return False, f"Error creating user: {str(e)}"

    @staticmethod
    def verify_otp(email: str, user_entered_otp: str, deactivate: bool = True) -> tuple[bool, str]:
        try:
            # Get the most recent active OTP for this email
            otp = EmailOTP.objects.filter(email=email, is_active=True).order_by('-created_at').first()
            if not otp:
                return False, "No active OTP found for this email"
            
            # Pass check_only=True when we don't want to deactivate
            is_valid, message = otp.is_valid(user_entered_otp, check_only=not deactivate)
            if is_valid:
                user = User.objects.get(email=email)
                user.is_active = True
                user.save()
                return True, "OTP verified successfully"
            return False, message
        except User.DoesNotExist:
            return False, "User does not exist"
        except Exception as e:
            return False, f"Error verifying OTP: {str(e)}"

    @staticmethod
    def request_password_reset(email: str) -> tuple[bool, str]:
        try:
            user = User.objects.filter(email=email).first()
            if not user:
                return False, "User does not exist"
            
            # Don't reset password yet - only send OTP for verification
            # Deactivate any existing active OTPs for this email
            EmailOTP.objects.filter(email=email, is_active=True).update(is_active=False)
            
            # Create new OTP
            otp = EmailOTP(email=email, code=EmailOTP.generate_otp())
            otp.save()
            send_otp_email(email, otp.code)
            return True, "OTP sent for password reset"
        except Exception as e:
            return False, f"Error requesting password reset: {str(e)}"

    @staticmethod
    def reset_password(email: str, new_password: str) -> tuple[bool, str]:
        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.force_password_change = False
            user.save()
            return True, "Password reset successfully"
        except User.DoesNotExist:
            return False, "User does not exist"
        except Exception as e:
            return False, f"Error resetting password: {str(e)}"

    @staticmethod
    def login_user(email: str) -> tuple[bool, str, dict[str, str | bool]]:
        try:
            user = User.objects.get(email=email, is_active=True)
            # Record login timestamp
            from django.utils import timezone
            user.last_login = timezone.now()
            user.save(update_fields=["last_login", "updated_at"])
            # Generate JWT token
            token = user.generate_token()
            has_password = user.password is not None and len(user.password) > 0
            return (
                True,
                "Login successful.",
                {
                    "token": token,
                    "has_password": has_password,
                    "terms_accepted": user.terms_accepted,
                    "force_password_change": user.force_password_change,
                    "email": user.email,
                    "role": user.role,
                    "school_id": user.school_id,
                    "school_name": user.school.name if user.school else None,
                },
            )
        except User.DoesNotExist:
            return False, "User does not exist", {}
        except Exception as e:
            return False, f"Error logging in: {str(e)}", {}

    @staticmethod
    def accept_terms(user_dto: UserDTO) -> tuple[bool, str]:
        try:
            user = User.from_dto(user_dto)
            user.accept_terms()
            return True, "Terms accepted successfully"
        except Exception as e:
            return False, f"Error accepting terms: {str(e)}"


def get_module_usage_count(module_name: str, student_ids: list[int]) -> int:
    """Return the number of distinct students (from *student_ids*) who have used a module.

    This is the single source of truth for module-usage counting.
    Every view that needs "students using module X" should call this.
    """
    if not student_ids:
        return 0

    if module_name == "domain_discovery":
        from domain_discovery.models import DomainSession
        return (
            DomainSession.objects.filter(user_id__in=student_ids)
            .values("user_id").distinct().count()
        )
    if module_name == "career_discovery":
        from career_discovery.models import CareerSession
        return (
            CareerSession.objects.filter(user_id__in=student_ids)
            .values("user_id").distinct().count()
        )
    return 0


def get_module_usage_count_for_school(module_name: str, school_id: int) -> int:
    """Convenience wrapper: count module usage across all students of a school."""
    student_ids = list(
        User.objects.filter(school_id=school_id, role="student")
        .values_list("id", flat=True)
    )
    return get_module_usage_count(module_name, student_ids)


def get_assigned_count_for_school(module_name: str, school_id: int) -> int:
    """Count distinct students with active school_assignment subscriptions for a module."""
    from .models import UserModuleSubscription

    return (
        UserModuleSubscription.objects.filter(
            school_subscription__school_id=school_id,
            module_name=module_name,
            source="school_assignment",
            is_active=True,
        )
        .values("user_id")
        .distinct()
        .count()
    )


def auto_assign_modules_for_student(user: "User") -> list[dict]:
    """Check GradeModuleAutoAssignment rules and create subscriptions for a newly added student."""
    from .models import GradeModuleAutoAssignment, UserModuleSubscription, User as UserModel

    if not user.school_id or not user.grade_level:
        return []

    rules = GradeModuleAutoAssignment.objects.filter(
        school_id=user.school_id,
        grade_level=user.grade_level,
        is_active=True,
        school_subscription__is_active=True,
    ).select_related("school_subscription", "created_by")

    created = []
    for rule in rules:
        # Skip if already assigned
        exists = UserModuleSubscription.objects.filter(
            user=user,
            module_name=rule.module_name,
            school_subscription=rule.school_subscription,
            is_active=True,
        ).exists()
        if exists:
            continue

        assignment = UserModuleSubscription.objects.create(
            user=user,
            module_name=rule.module_name,
            expiry_date=rule.school_subscription.expiry_date,
            is_active=True,
            source="school_assignment",
            school_subscription=rule.school_subscription,
            assigned_by=rule.created_by,
        )
        created.append({
            "id": assignment.id,
            "user_id": user.id,
            "module_name": rule.module_name,
        })
    return created
