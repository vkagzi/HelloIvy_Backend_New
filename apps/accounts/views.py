from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema

from utils.user_dto_view import UserDTOView

from .services import AccountsService

from .serializers import (
    AdminUserCreateSerializer,
    BulkUserImportSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    OTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SignupSerializer,
    UserModuleSubscriptionSerializer,
)
from .roles import UserRole
from .models import EmailOTP, ModuleName, MODULE_META, ModulePricing, School, SchoolModuleSubscription, User


class SignupView(APIView):

    allow_public = True  # Allow public access for signup

    @extend_schema(request=SignupSerializer)
    def post(self, request: Request) -> Response:
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            (success, reason) = AccountsService.create_user(
                email=serializer.validated_data["email"]
            )
            if not success:
                return Response({"error": reason}, status=400)

            return Response({"message": "Signup successful. OTP sent."}, status=201)
        return Response(serializer.errors, status=400)


class OTPVerifyView(APIView):

    allow_public = True  # Allow public access for signup

    @extend_schema(
        request=OTPVerifySerializer,
    )
    def post(self, request: Request) -> Response:
        serializer = OTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Never deactivate OTP during verification
                # It will be deactivated when the user sets their password
                (success, reason) = AccountsService.verify_otp(
                    email=serializer.validated_data["email"],
                    user_entered_otp=serializer.validated_data["code"],
                    deactivate=False,
                )
                if success:
                    (
                        login_response_success,
                        login_response_reason,
                        login_response_data,
                    ) = AccountsService.login_user(
                        email=serializer.validated_data["email"]
                    )
                    if login_response_success:
                        return Response(
                            login_response_data,
                            status=200,
                        )
                    return Response({"error": login_response_reason}, status=400)
                return Response({"error": reason}, status=400)
            except EmailOTP.DoesNotExist:
                return Response(
                    {"error": "No active OTP found for this email"}, status=400
                )
            except User.DoesNotExist:
                return Response({"error": "User does not exist"}, status=400)
            except Exception as e:
                return Response({"error": f"Error verifying OTP: {str(e)}"}, status=400)
        return Response(serializer.errors, status=400)


class LoginView(APIView):

    allow_public = True  # Allow public access for signup

    @extend_schema(
        request=LoginSerializer,
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.filter(email=serializer.validated_data["email"]).first()
            if not user:
                return Response({"error": "User does not exist."}, status=400)
            
            if not user.is_active:
                return Response({"error": "Account not verified. Please verify your email first."}, status=400)
            
            # Check if user has a password
            if not user.password or len(user.password) == 0:
                return Response({"error": "Please set up your password first."}, status=400)
            
            if not user.check_password(serializer.validated_data["password"]):
                return Response({"error": "Invalid email or password."}, status=400)

            (
                login_response_success,
                login_response_reason,
                login_response_data,
            ) = AccountsService.login_user(email=serializer.validated_data["email"])
            if login_response_success:
                return Response(
                    login_response_data,
                    status=200,
                )
            return Response({"error": login_response_reason}, status=400)
        return Response(serializer.errors, status=400)


class PasswordResetRequestView(APIView):

    allow_public = True  # Allow public access for signup

    @extend_schema(
        request=PasswordResetRequestSerializer,
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            (success, reason) = AccountsService.request_password_reset(
                email=serializer.validated_data["email"]
            )
            if success:
                return Response({"message": reason}, status=200)
            return Response({"error": reason}, status=400)
        return Response(serializer.errors, status=400)


class PasswordResetConfirmView(APIView):

    allow_public = True  # Allow public access for password reset

    @extend_schema(
        request=PasswordResetConfirmSerializer,
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Verify the OTP is still valid
                otp = EmailOTP.objects.filter(
                    email=serializer.validated_data["email"],
                    is_active=True
                ).order_by('-created_at').first()
                
                if not otp:
                    return Response({"error": "No active OTP found for this email"}, status=400)
                
                # Validate and deactivate the OTP (check_only=False)
                is_valid, message = otp.is_valid(serializer.validated_data["code"], check_only=False)
                if not is_valid:
                    return Response({"error": message}, status=400)
                
                # Reset the password
                (success, reason) = AccountsService.reset_password(
                    email=serializer.validated_data["email"],
                    new_password=serializer.validated_data["new_password"],
                )
                if success:
                    return Response({"message": reason}, status=200)
                return Response({"error": reason}, status=400)
            except Exception as e:
                return Response(
                    {"error": f"Error resetting password: {str(e)}"}, status=400
                )
        return Response(serializer.errors, status=400)


class MeView(UserDTOView):
    """
    Returns the current authenticated user's info.
    """

    @extend_schema(request=None, responses={200: "Current user info."})
    def get(self, request: Request) -> Response:
        # user_dto is set by UserDTOView
        first_name = self.user_dto.first_name
        last_name = self.user_dto.last_name
        name = f"{first_name} {last_name}".strip() or None
        user_data = {
            "id": self.user_dto.id,
            "email": self.user_dto.email,
            "first_name": first_name,
            "last_name": last_name,
            "name": name,
            "is_active": getattr(self.user_dto, "is_active", None),
            "role": self.user_dto.role,
            "school_id": self.user_dto.school_id,
            "school_name": self.user_dto.school_name,
            "terms_accepted": self.user_dto.terms_accepted,
            "force_password_change": self.user_dto.force_password_change,
        }
        return Response(user_data, status=200)

    @extend_schema(request=None, responses={200: "User info updated."})
    def patch(self, request: Request) -> Response:
        user = User.objects.get(id=self.user_dto.id)
        data = request.data

        if "first_name" in data:
            user.first_name = data["first_name"] or ""
        if "last_name" in data:
            user.last_name = data["last_name"] or ""

        user.save(update_fields=["first_name", "last_name", "updated_at"])

        first_name = user.first_name
        last_name = user.last_name
        name = f"{first_name} {last_name}".strip() or None
        return Response({
            "id": user.id,
            "email": user.email,
            "first_name": first_name,
            "last_name": last_name,
            "name": name,
        }, status=200)


class ModuleChoicesView(APIView):
    """Returns all available module names, display labels, icons, colors and default prices."""

    allow_public = True

    def get(self, request: Request) -> Response:
        from .payment_views import FALLBACK_PRICES
        # Build a global price lookup from the DB
        global_prices = {
            mp.module_name: int(mp.price)
            for mp in ModulePricing.objects.filter(
                school__isnull=True, user__isnull=True, is_active=True
            )
        }
        default_price = 999

        modules = [
            {
                "value": m.value,
                "label": m.label,
                "price": global_prices.get(m.value, FALLBACK_PRICES.get(m.value, default_price)),
                **MODULE_META.get(m.value, {}),
            }
            for m in ModuleName
        ]

        # Add custom modules from database
        from .models import CustomModule
        is_admin = False
        user = request.user
        if user and user.is_authenticated:
            role = getattr(user, "role", None)
            is_admin = role in ("superadmin", "operationadmin")

        for cm in CustomModule.objects.all():
            if cm.value in global_prices or is_admin:
                modules.append({
                    "value": cm.value,
                    "label": cm.label,
                    "price": global_prices.get(cm.value, default_price),
                    "icon": cm.icon,
                    "color": cm.color,
                })

        return Response({"modules": modules}, status=200)


class AcademicLevelsView(APIView):
    """Returns all academic levels and their associated grade levels."""

    allow_public = True

    def get(self, request: Request) -> Response:
        academic_levels = [
            {"value": al.value, "label": al.label}
            for al in User.AcademicLevel
        ]
        return Response(
            {
                "academic_levels": academic_levels,
                "grade_levels": User.GRADE_LEVELS,
            },
            status=200,
        )


class MyModulesView(UserDTOView):
    """
    Returns the list of active module names accessible to the current user.
    Access can come from:
      - A SchoolModuleSubscription for the user's school (school-level, for students and school admins)
      - A UserModuleSubscription record directly on the user (individual-level, students only)
    Superadmin and operationadmin have access to all modules.
    School admins only see modules their school has an active subscription for.
    """

    @extend_schema(request=None, responses={200: "Active modules for the user."})
    def get(self, request: Request) -> Response:
        from django.utils import timezone
        from .models import UserModuleSubscription, SchoolModuleSubscription, ModuleName, CustomModule, ModulePricing

        # Superadmin and operationadmin bypass subscription checks
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            global_prices = {
                mp.module_name for mp in ModulePricing.objects.filter(
                    school__isnull=True, user__isnull=True, is_active=True
                )
            }
            all_module_names = [m.value for m in ModuleName] + [
                cm.value for cm in CustomModule.objects.all() if cm.value in global_prices
            ]
            
            # For admins, give a fake far-future expiry date
            fake_expiry = (timezone.now() + timezone.timedelta(days=36500)).date().isoformat()
            module_details = [
                {"module_name": name, "expiry_date": fake_expiry, "is_expired": False}
                for name in all_module_names
            ]
            
            return Response({
                "modules": all_module_names,
                "module_details": module_details
            }, status=200)

        today = timezone.now().date()
        recent_cutoff = today - timezone.timedelta(days=30)
        
        # We'll use a dict to keep the "best" subscription for each module
        # Priority: Active (latest expiry) > Expired (latest expiry)
        module_info: dict[str, dict] = {}

        def update_module_info(name, expiry, is_active):
            is_expired = expiry < today
            if name not in module_info:
                module_info[name] = {
                    "module_name": name,
                    "expiry_date": expiry.isoformat(),
                    "is_expired": is_expired
                }
            else:
                existing = module_info[name]
                # If existing is expired and new one is not, or new one has later expiry
                if (existing["is_expired"] and not is_expired) or (expiry.isoformat() > existing["expiry_date"]):
                     module_info[name] = {
                        "module_name": name,
                        "expiry_date": expiry.isoformat(),
                        "is_expired": is_expired
                    }

        # School-level subscriptions
        if self.user_dto.school_id:
            school_subs = SchoolModuleSubscription.objects.filter(
                school_id=self.user_dto.school_id,
                is_active=True,
                expiry_date__gte=recent_cutoff,
            )
            for sub in school_subs:
                update_module_info(sub.module_name, sub.expiry_date, sub.is_active)

        # Individual user-level subscriptions
        if self.user_dto.role == UserRole.STUDENT:
            user_subs = UserModuleSubscription.objects.filter(
                user_id=self.user_dto.id,
                is_active=True,
                expiry_date__gte=recent_cutoff,
            )
            for sub in user_subs:
                update_module_info(sub.module_name, sub.expiry_date, sub.is_active)

        active_modules = [name for name, info in module_info.items() if not info["is_expired"]]
        
        return Response({
            "modules": active_modules,
            "module_details": list(module_info.values())
        }, status=200)


class CustomModuleListCreateView(APIView):
    """
    List and create custom modules.
    GET is public so that both admin and students can read custom modules (e.g. for selection dropdowns).
    POST requires admin permission.
    """
    allow_public = True  # We let GET be public, but check role in POST

    def get(self, request: Request) -> Response:
        from .models import CustomModule
        from .serializers import CustomModuleSerializer
        cms = CustomModule.objects.all().order_by("-created_at")
        serializer = CustomModuleSerializer(cms, many=True)
        return Response({"modules": serializer.data}, status=200)

    def post(self, request: Request) -> Response:
        # Require admin to create
        user = request.user
        role = getattr(user, "role", None)
        if role not in ("superadmin", "operationadmin"):
            raise PermissionDenied(detail="Only superadmins and operationadmins can create custom modules")
        from .serializers import CustomModuleSerializer
        serializer = CustomModuleSerializer(data=request.data)
        if serializer.is_valid():
            custom_module = serializer.save()
            price_val = request.data.get("price")
            if price_val is not None and str(price_val).strip() != "":
                from .models import ModulePricing
                ModulePricing.objects.update_or_create(
                    module_name=custom_module.value,
                    school__isnull=True,
                    user__isnull=True,
                    defaults={
                        "price": price_val,
                        "is_active": True
                    }
                )
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class CustomModuleDetailView(APIView):
    """
    Retrieve or delete a custom module.
    """
    allow_public = False

    def delete(self, request: Request, value: str) -> Response:
        user = request.user
        role = getattr(user, "role", None)
        if role not in ("superadmin", "operationadmin"):
            raise PermissionDenied(detail="Only superadmins and operationadmins can delete custom modules")
        from .models import CustomModule, ModulePricing
        cm = CustomModule.objects.filter(value=value).first()
        if not cm:
            return Response({"detail": "Custom module not found"}, status=404)
        cm.delete()
        ModulePricing.objects.filter(module_name=value).delete()
        return Response({"message": "Custom module deleted successfully"}, status=200)


class AdminUserModuleView(UserDTOView):
    """List and add module subscriptions for a specific user (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="Admin access required")

    def get(self, request: Request, user_id: int) -> Response:
        self._require_admin()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
        from .models import UserModuleSubscription
        subs = UserModuleSubscription.objects.filter(user=user).order_by("module_name")
        return Response(
            {"subscriptions": UserModuleSubscriptionSerializer(subs, many=True).data},
            status=200,
        )

    def post(self, request: Request, user_id: int) -> Response:
        self._require_admin()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
        serializer = UserModuleSubscriptionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class AdminUserModuleDetailView(UserDTOView):
    """Edit or delete a single user module subscription (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    def patch(self, request: Request, user_id: int, sub_id: int) -> Response:
        self._require_admin()
        from .models import UserModuleSubscription
        try:
            sub = UserModuleSubscription.objects.get(id=sub_id, user_id=user_id)
        except UserModuleSubscription.DoesNotExist:
            return Response({"error": "Subscription not found"}, status=404)
        serializer = UserModuleSubscriptionSerializer(sub, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request: Request, user_id: int, sub_id: int) -> Response:
        self._require_admin()
        from .models import UserModuleSubscription
        try:
            sub = UserModuleSubscription.objects.get(id=sub_id, user_id=user_id)
        except UserModuleSubscription.DoesNotExist:
            return Response({"error": "Subscription not found"}, status=404)
        sub.delete()
        return Response(status=204)


class AcceptTermsView(UserDTOView):
    """
    View to accept terms and conditions.
    """

    @extend_schema(
        request=None,
        responses={200: "Terms accepted successfully."},
    )
    def post(self, request: Request) -> Response:
        AccountsService.accept_terms(self.user_dto)
        return Response({"message": "Terms accepted successfully."}, status=200)


class ChangePasswordView(UserDTOView):
    """
    Authenticated endpoint to change password.
    Clears force_password_change flag after success.
    """

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: "Password changed successfully."},
    )
    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.get(id=self.user_dto.id)
            if not user.check_password(serializer.validated_data["current_password"]):
                return Response({"error": "Current password is incorrect."}, status=400)
            user.set_password(serializer.validated_data["new_password"])
            user.force_password_change = False
            user.save(update_fields=["password", "force_password_change", "updated_at"])
            return Response({"message": "Password changed successfully."}, status=200)
        return Response(serializer.errors, status=400)


class SettingsView(UserDTOView):
    """GET/PUT user settings stored as a JSON blob."""

    @extend_schema(request=None, responses={200: "User settings."})
    def get(self, request: Request) -> Response:
        user = User.objects.get(id=self.user_dto.id)
        return Response({"settings": user.settings}, status=200)

    @extend_schema(request=None, responses={200: "Settings updated."})
    def put(self, request: Request) -> Response:
        if not isinstance(request.data, dict):
            return Response({"error": "Payload must be a JSON object."}, status=400)

        user = User.objects.get(id=self.user_dto.id)
        # Merge incoming keys into existing settings
        user.settings.update(request.data)
        user.save(update_fields=["settings", "updated_at"])
        return Response({"settings": user.settings}, status=200)


class AdminDashboardView(UserDTOView):
    """Admin dashboard with basic statistics."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(request=None, responses={200: "Admin dashboard statistics."})
    def get(self, request: Request) -> Response:
        self._require_admin()

        # Schooladmins see only their school's stats
        if self.user_dto.role == UserRole.SCHOOLADMIN and self.user_dto.school_id:
            users_qs = User.objects.filter(school_id=self.user_dto.school_id, role=UserRole.STUDENT)
        else:
            users_qs = User.objects.all()

        total_users = users_qs.count()
        active_users = users_qs.filter(is_active=True).count()
        role_counts = {
            role.value: users_qs.filter(role=role).count()
            for role in User.Role
        }
        return Response({
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "role_counts": role_counts,
        }, status=200)


class AdminUsersView(UserDTOView):
    """List all users (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(request=None, responses={200: "List of all users."})
    def get(self, request: Request) -> Response:
        self._require_admin()

        # Schooladmins see only their school's students
        if self.user_dto.role == UserRole.SCHOOLADMIN and self.user_dto.school_id:
            users = User.objects.filter(
                school_id=self.user_dto.school_id, role=UserRole.STUDENT
            ).order_by("-created_at")
        else:
            users = User.objects.all().order_by("-created_at")

        users_data = [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "role": u.role,
                "is_active": u.is_active,
                "terms_accepted": u.terms_accepted,
                "school_id": u.school_id,
                "school_name": u.school.name if u.school else None,
                "academic_level": u.academic_level,
                "grade_level": u.grade_level,
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "created_at": u.created_at.isoformat(),
                "updated_at": u.updated_at.isoformat(),
            }
            for u in users.select_related("school")
        ]
        return Response({"users": users_data}, status=200)

    @extend_schema(request=AdminUserCreateSerializer, responses={201: "User created."})
    def post(self, request: Request) -> Response:
        """Create a new user (superadmin or schooladmin for own school's students)."""
        is_superadmin = self.user_dto.role == UserRole.SUPERADMIN
        is_schooladmin = self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN)

        if not is_superadmin and not is_schooladmin:
            raise PermissionDenied(detail="Only superadmins and school admins can create users")

        serializer = AdminUserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data

        # Schooladmins/schoolopsadmins can only create students for their own school
        if is_schooladmin:
            if data["role"] != UserRole.STUDENT:
                raise PermissionDenied(detail="School admins can only create student accounts")
            if not self.user_dto.school_id:
                raise PermissionDenied(detail="Your account is not associated with a school")
            data["school_id"] = self.user_dto.school_id

        if User.objects.filter(email=data["email"]).exists():
            return Response({"email": ["A user with this email already exists."]}, status=400)

        school = None
        school_id = data.get("school_id")
        if school_id:
            try:
                school = School.objects.get(id=school_id)
            except School.DoesNotExist:
                return Response({"school_id": ["School not found."]}, status=400)

        from django.contrib.auth.hashers import make_password
        import secrets
        from utils.email import send_temp_password_email, send_school_admin_welcome_email
        temp_password = secrets.token_urlsafe(10)
        user_kwargs = dict(
            email=data["email"],
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            password=make_password(temp_password),
            role=data["role"],
            school=school,
            is_active=data.get("is_active", True),
            force_password_change=True,
        )
        # schooladmin users don't have academic/grade levels
        if data["role"] != UserRole.SCHOOLADMIN:
            user_kwargs["academic_level"] = data.get("academic_level")
            user_kwargs["grade_level"] = data.get("grade_level")
        user = User.objects.create(**user_kwargs)
        email_sent = False
        if data.get("send_password_email", True):
            try:
                if data["role"] == UserRole.SCHOOLADMIN and school:
                    send_school_admin_welcome_email(user.email, temp_password, school.name)
                else:
                    student_name = f"{user.first_name} {user.last_name}".strip()
                    send_temp_password_email(user.email, temp_password, student_name=student_name)
                email_sent = True
            except Exception as e:
                print(f"[ADMIN CREATE USER] Email failed for {user.email}: {e}")
        return Response({
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "school_id": user.school_id,
            "is_active": user.is_active,
            "academic_level": user.academic_level,
            "grade_level": user.grade_level,
            "email_sent": email_sent,
        }, status=201)


class AdminBulkImportValidateView(UserDTOView):
    """Validate a list of emails for bulk import."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(request=None, responses={200: "Validation results."})
    def post(self, request: Request) -> Response:
        self._require_admin()

        emails = request.data.get("emails", [])
        if not isinstance(emails, list):
            return Response({"error": "emails must be a list"}, status=400)

        import re
        email_regex = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

        valid = []
        invalid = []
        seen = set()

        for email in emails:
            email_lower = email.strip().lower()
            if not email_lower:
                continue
            if email_lower in seen:
                invalid.append({"email": email_lower, "reason": "Duplicate in list"})
                continue
            seen.add(email_lower)

            if not email_regex.match(email_lower):
                invalid.append({"email": email_lower, "reason": "Invalid email format"})
                continue

            if User.objects.filter(email=email_lower).exists():
                invalid.append({"email": email_lower, "reason": "Already exists in database"})
                continue

            valid.append(email_lower)

        return Response({"valid": valid, "invalid": invalid}, status=200)


class AdminBulkImportView(UserDTOView):
    """Bulk import users by creating accounts and sending temp passwords."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(request=BulkUserImportSerializer, responses={201: "Bulk import results."})
    def post(self, request: Request) -> Response:
        self._require_admin()

        serializer = BulkUserImportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        role = data["role"]
        school_id = data.get("school_id")

        academic_level = data.get("academic_level")
        grade_level = data.get("grade_level")
        send_password_email = data.get("send_password_email", True)

        # Schooladmins/schoolopsadmins can only add to their own school
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if role not in (UserRole.STUDENT, UserRole.SCHOOLADMIN):
                raise PermissionDenied(detail="School admins can only create students or school admins")
            school_id = self.user_dto.school_id
            if not school_id:
                return Response({"error": "Your account is not associated with a school"}, status=400)
            # Schooladmins can only assign high_school to students
            if role == UserRole.STUDENT:
                if academic_level and academic_level != "high_school":
                    return Response(
                        {"academic_level": ["School admins can only assign high_school academic level to students."]},
                        status=400,
                    )

        # Superadmins must provide school_id
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            if not school_id:
                return Response({"school_id": ["School is required for bulk import"]}, status=400)

        # Validate school exists
        school = None
        if school_id:
            try:
                school = School.objects.get(id=school_id)
            except School.DoesNotExist:
                return Response({"school_id": ["School not found."]}, status=400)

        import secrets
        from django.contrib.auth.hashers import make_password
        from utils.email import send_temp_password_email, send_school_admin_welcome_email

        created = []
        failed = []

        for user_item in data["users"]:
            email_lower = user_item["email"].strip().lower()
            first_name = user_item.get("first_name", "") or ""
            last_name = user_item.get("last_name", "") or ""
            try:
                if User.objects.filter(email=email_lower).exists():
                    failed.append({"email": email_lower, "reason": "Already exists"})
                    continue

                temp_password = secrets.token_urlsafe(10)
                user_kwargs = dict(
                    email=email_lower,
                    password=make_password(temp_password),
                    role=role,
                    school=school,
                    is_active=True,
                    first_name=first_name,
                    last_name=last_name,
                    force_password_change=True,
                )
                # schooladmin users don't have academic/grade levels
                if role != UserRole.SCHOOLADMIN:
                    user_kwargs["academic_level"] = academic_level
                    user_kwargs["grade_level"] = grade_level
                user = User.objects.create(**user_kwargs)

                # Auto-assign modules based on grade rules for new students
                if role == UserRole.STUDENT and school and grade_level:
                    from .services import auto_assign_modules_for_student
                    auto_assign_modules_for_student(user)

                if send_password_email:
                    try:
                        if role == UserRole.SCHOOLADMIN and school:
                            send_school_admin_welcome_email(email_lower, temp_password, school.name)
                        else:
                            student_name = f"{first_name} {last_name}".strip()
                            send_temp_password_email(email_lower, temp_password, student_name=student_name)
                        created.append({"email": email_lower, "id": user.id, "email_sent": True})
                    except Exception as e:
                        print(f"[BULK IMPORT] Email failed for {email_lower}: {e}")
                        created.append({"email": email_lower, "id": user.id, "email_sent": False})
                else:
                    created.append({"email": email_lower, "id": user.id, "email_sent": False})

            except Exception as e:
                failed.append({"email": email_lower, "reason": str(e)})

        return Response({
            "total_submitted": len(data["users"]),
            "total_created": len(created),
            "total_failed": len(failed),
            "created": created,
            "failed": failed,
        }, status=201)


class AdminUserDetailView(UserDTOView):
    """Detailed info for a single user (admin only)."""

    def _require_admin(self, user_id: int | None = None) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="Admin access required")
        # Schooladmins/schoolopsadmins can only view students in their school
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN) and user_id:
            try:
                target_user = User.objects.get(id=user_id)
                if target_user.school_id != self.user_dto.school_id:
                    raise PermissionDenied(detail="Access denied to this student")
            except User.DoesNotExist:
                pass

    @extend_schema(request=None, responses={200: "User detail with module stats."})
    def get(self, request: Request, user_id: int) -> Response:
        self._require_admin(user_id=user_id)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        from domain_discovery.models import DomainSession
        from career_discovery.models import CareerSession
        from apps.profiles.models import UserProfile
        from apps.accounts.models import UserModuleSubscription

        domain_sessions = DomainSession.objects.filter(user=user)
        career_sessions = CareerSession.objects.filter(user=user)

        # Use model fields for name
        first_name = user.first_name
        last_name = user.last_name
        profile_json_data = None
        try:
            profile = UserProfile.objects.get(user_id=user.id)

            # Include full profile data when requested
            include_profile = request.query_params.get("include_profile", "").lower() in ("true", "1")
            if include_profile:
                profile_json_data = profile.profile_json
        except UserProfile.DoesNotExist:
            pass

        response_data = {
            "id": user.id,
            "email": user.email,
            "first_name": first_name,
            "last_name": last_name,
            "role": user.role,
            "is_active": user.is_active,
            "terms_accepted": user.terms_accepted,
            "school_id": user.school_id,
            "school_name": user.school.name if user.school else None,
            "academic_level": user.academic_level,
            "grade_level": user.grade_level,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
            "modules": {
                "domain_discovery": {
                    "total_sessions": domain_sessions.count(),
                    "completed_sessions": sum(1 for s in domain_sessions if s.is_completed),
                    "sessions": [
                        {
                            "session_id": str(s.session_id),
                            "current_step": s.current_step,
                            "total_steps": s.total_steps,
                            "is_completed": s.is_completed,
                            "is_active": s.is_active,
                            "created_at": s.created_at.isoformat(),
                        }
                        for s in domain_sessions.order_by("-created_at")
                    ],
                },
                "career_discovery": {
                    "total_sessions": career_sessions.count(),
                    "completed_sessions": sum(1 for s in career_sessions if s.is_completed),
                    "sessions": [
                        {
                            "session_id": str(s.session_id),
                            "current_step": s.current_step,
                            "total_steps": s.total_steps,
                            "current_phase": s.current_phase,
                            "is_completed": s.is_completed,
                            "is_active": s.is_active,
                            "created_at": s.created_at.isoformat(),
                        }
                        for s in career_sessions.order_by("-created_at")
                    ],
                },
            },
        }

        if profile_json_data is not None:
            # Override personalDetails firstName/lastName with User model values
            profile = profile_json_data.get("profile") if isinstance(profile_json_data, dict) else None
            if isinstance(profile, dict):
                personal = profile.get("personalDetails")
                if isinstance(personal, dict):
                    personal.pop("firstName", None)
                    personal.pop("lastName", None)
            response_data["profile_data"] = profile_json_data

        # Include assigned modules
        assigned_modules = UserModuleSubscription.objects.filter(
            user=user, is_active=True, source="school_assignment"
        )
        response_data["assigned_modules"] = [
            {"id": sub.id, "module_name": sub.module_name}
            for sub in assigned_modules
        ]

        return Response(response_data, status=200)

    @extend_schema(request=None, responses={200: "User updated."})
    def patch(self, request: Request, user_id: int) -> Response:
        """Update user details, change password, or deactivate."""
        is_superadmin = self.user_dto.role == UserRole.SUPERADMIN
        is_school_admin = self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN)

        if not is_superadmin and not is_school_admin:
            raise PermissionDenied(detail="Admin access required")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        # School admins can only edit students belonging to their own school
        if is_school_admin:
            if user.school_id != self.user_dto.school_id:
                raise PermissionDenied(detail="Access denied to this student")
            if user.role != UserRole.STUDENT:
                raise PermissionDenied(detail="School admins can only edit student accounts")
            # School admins may not change sensitive fields
            restricted_fields = {"role", "school_id", "password"}
            for field in restricted_fields:
                if field in request.data:
                    raise PermissionDenied(detail=f"School admins cannot modify '{field}'")

        data = request.data

        # Change password
        new_password = data.get("password")
        if new_password:
            if len(new_password) < 8:
                return Response({"error": "Password must be at least 8 characters"}, status=400)
            from django.contrib.auth.hashers import make_password
            user.password = make_password(new_password)
            user.force_password_change = True

        # Update role
        if "role" in data:
            valid_roles = [r[0] for r in User.Role.choices]
            if data["role"] not in valid_roles:
                return Response({"error": f"Invalid role. Must be one of: {valid_roles}"}, status=400)
            user.role = data["role"]

        # Update school
        if "school_id" in data:
            school_id = data["school_id"]
            if school_id is None:
                user.school = None
            else:
                try:
                    user.school = School.objects.get(id=school_id)
                except School.DoesNotExist:
                    return Response({"error": "School not found"}, status=400)

        # Update is_active
        if "is_active" in data:
            user.is_active = bool(data["is_active"])

        # Update academic_level
        if "academic_level" in data:
            academic_level = data["academic_level"]
            if academic_level is not None:
                valid_levels = [c[0] for c in User.AcademicLevel.choices]
                if academic_level not in valid_levels:
                    return Response(
                        {"error": f"Invalid academic_level. Must be one of: {valid_levels}"},
                        status=400,
                    )
            user.academic_level = academic_level

        # Update grade_level
        if "grade_level" in data:
            grade_level = data["grade_level"]
            if grade_level is not None:
                al = data.get("academic_level", user.academic_level)
                if not al:
                    return Response(
                        {"error": "academic_level is required when setting grade_level."},
                        status=400,
                    )
                valid_grades = User.GRADE_LEVELS.get(al, [])
                if grade_level not in valid_grades:
                    return Response(
                        {"error": f"Invalid grade_level for {al}. Must be one of: {valid_grades}"},
                        status=400,
                    )
            user.grade_level = grade_level

        # Update first_name
        if "first_name" in data:
            user.first_name = data["first_name"] or ""

        # Update last_name
        if "last_name" in data:
            user.last_name = data["last_name"] or ""

        user.save()

        return Response({
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "school_id": user.school_id,
            "school_name": user.school.name if user.school else None,
            "academic_level": user.academic_level,
            "grade_level": user.grade_level,
        }, status=200)


class AdminSessionMessagesView(UserDTOView):
    """Fetch all messages for a given session (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(request=None, responses={200: "Session messages."})
    def get(self, request: Request, module: str, session_id: str) -> Response:
        self._require_admin()

        if module == "domain":
            from domain_discovery.models import DomainSession, DomainMessage
            try:
                session_obj = DomainSession.objects.get(session_id=session_id)
            except DomainSession.DoesNotExist:
                return Response({"error": "Session not found"}, status=404)
            messages = DomainMessage.objects.filter(session=session_obj).order_by("timestamp")
            data = [
                {
                    "message_id": m.message_id,
                    "type": m.type,
                    "content": m.content,
                    "question_type": m.question_type,
                    "medium": m.medium,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in messages
            ]
        elif module == "career":
            from career_discovery.models import CareerSession, CareerMessage
            try:
                session_obj = CareerSession.objects.get(session_id=session_id)
            except CareerSession.DoesNotExist:
                return Response({"error": "Session not found"}, status=404)
            messages = CareerMessage.objects.filter(session=session_obj).order_by("timestamp")
            data = [
                {
                    "message_id": m.message_id,
                    "type": m.type,
                    "content": m.content,
                    "phase": m.phase,
                    "step_number": m.step_number,
                    "medium": m.medium,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in messages
            ]
        else:
            return Response({"error": "Invalid module"}, status=400)

        return Response({"messages": data}, status=200)


class AdminSessionReportView(UserDTOView):
    """Fetch recommendations / report for a completed session (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(request=None, responses={200: "Session report."})
    def get(self, request: Request, module: str, session_id: str) -> Response:
        self._require_admin()

        if module == "domain":
            from domain_discovery.models import DomainSession, DomainRecommendation
            try:
                session_obj = DomainSession.objects.get(session_id=session_id)
            except DomainSession.DoesNotExist:
                return Response({"error": "Session not found"}, status=404)
            recs = DomainRecommendation.objects.filter(session=session_obj).order_by("rank")
            data = {
                "session_id": session_id,
                "student_email": session_obj.user.email,
                "notes": session_obj.notes,
                "riasec_scores": session_obj.riasec_scores,
                "started_at": session_obj.created_at.isoformat(),
                "completed_at": session_obj.updated_at.isoformat(),
                "recommendations": [
                    {
                        "domain_title": r.domain_title,
                        "category": r.category,
                        "match_percentage": r.match_percentage,
                        "description": r.description,
                        "why_recommended": r.why_recommended,
                        "key_interests": r.key_interests,
                        "sub_domains": r.sub_domains,
                        "related_subjects": r.related_subjects,
                        "exploration_activities": r.exploration_activities,
                        "potential_careers": r.potential_careers,
                        "rank": r.rank,
                    }
                    for r in recs
                ],
            }
        elif module == "career":
            from career_discovery.models import CareerSession, CareerRecommendation
            try:
                session_obj = CareerSession.objects.get(session_id=session_id)
            except CareerSession.DoesNotExist:
                return Response({"error": "Session not found"}, status=404)
            recs = CareerRecommendation.objects.filter(session=session_obj).order_by("rank")
            data = {
                "session_id": session_id,
                "student_email": session_obj.user.email,
                "notes": session_obj.notes,
                "started_at": session_obj.created_at.isoformat(),
                "completed_at": session_obj.updated_at.isoformat(),
                "recommendations": [
                    {
                        "career_title": r.career_title,
                        "salary_range": r.salary_range,
                        "match_percentage": r.match_percentage,
                        "description": r.description,
                        "why_recommended": r.why_recommended,
                        "required_skills": r.required_skills,
                        "next_steps": r.next_steps,
                        "alignment_points": r.alignment_points,
                        "related_subjects": r.related_subjects,
                        "day_in_life": r.day_in_life,
                        "pros_and_cons": r.pros_and_cons,
                        "work_life_balance": r.work_life_balance,
                        "rank": r.rank,
                    }
                    for r in recs
                ],
            }
        else:
            return Response({"error": "Invalid module"}, status=400)

        return Response(data, status=200)


class AdminUserCommentView(UserDTOView):
    """GET / PATCH counselor and parent/student comments for a user (admin only)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="Admin access required")

    def get(self, request: Request, user_id: int) -> Response:
        self._require_admin()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
        return Response({
            "counselor_comment": user.counselor_comment,
            "counselor_comment_updated_at": user.counselor_comment_updated_at.isoformat() if user.counselor_comment_updated_at else None,
            "parent_student_comment": user.parent_student_comment,
            "parent_student_comment_updated_at": user.parent_student_comment_updated_at.isoformat() if user.parent_student_comment_updated_at else None,
        }, status=200)

    def patch(self, request: Request, user_id: int) -> Response:
        self._require_admin()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        from django.utils import timezone
        now = timezone.now()

        is_superadmin = self.user_dto.role == UserRole.SUPERADMIN

        if "counselor_comment" in request.data:
            user.counselor_comment = request.data["counselor_comment"]
            user.counselor_comment_updated_at = now

        # Non-superadmin admins (counselors) cannot edit student/parent comments
        if "parent_student_comment" in request.data:
            if not is_superadmin:
                return Response({"error": "Only superadmins can edit student/parent comments"}, status=403)
            user.parent_student_comment = request.data["parent_student_comment"]
            user.parent_student_comment_updated_at = now

        user.save(update_fields=[
            "counselor_comment", "counselor_comment_updated_at",
            "parent_student_comment", "parent_student_comment_updated_at",
        ])

        return Response({
            "counselor_comment": user.counselor_comment,
            "counselor_comment_updated_at": user.counselor_comment_updated_at.isoformat() if user.counselor_comment_updated_at else None,
            "parent_student_comment": user.parent_student_comment,
            "parent_student_comment_updated_at": user.parent_student_comment_updated_at.isoformat() if user.parent_student_comment_updated_at else None,
        }, status=200)


class StudentCommentView(UserDTOView):
    """GET / PATCH comments for the logged-in student's own record.
    Students can read both sides but only edit their own (parent_student_comment).
    """

    def get(self, request: Request) -> Response:
        user = User.objects.get(id=self.user_dto.id)
        return Response({
            "counselor_comment": user.counselor_comment,
            "counselor_comment_updated_at": user.counselor_comment_updated_at.isoformat() if user.counselor_comment_updated_at else None,
            "parent_student_comment": user.parent_student_comment,
            "parent_student_comment_updated_at": user.parent_student_comment_updated_at.isoformat() if user.parent_student_comment_updated_at else None,
        }, status=200)

    def patch(self, request: Request) -> Response:
        user = User.objects.get(id=self.user_dto.id)

        from django.utils import timezone
        now = timezone.now()

        # Students can only update their own parent/student comment
        if "parent_student_comment" in request.data:
            user.parent_student_comment = request.data["parent_student_comment"]
            user.parent_student_comment_updated_at = now

        # Silently ignore any attempt to set counselor_comment
        user.save(update_fields=[
            "parent_student_comment", "parent_student_comment_updated_at",
        ])

        return Response({
            "counselor_comment": user.counselor_comment,
            "counselor_comment_updated_at": user.counselor_comment_updated_at.isoformat() if user.counselor_comment_updated_at else None,
            "parent_student_comment": user.parent_student_comment,
            "parent_student_comment_updated_at": user.parent_student_comment_updated_at.isoformat() if user.parent_student_comment_updated_at else None,
        }, status=200)


class AdminSendEmailView(UserDTOView):
    """Admin/counselor sends an email to a student."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN, UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(request=None, responses={200: "Email sent."})
    def post(self, request: Request, user_id: int) -> Response:
        self._require_admin()
        try:
            student = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        # School admins can only email students in their own school
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if student.school_id != self.user_dto.school_id:
                raise PermissionDenied(detail="Access denied to this student")

        subject = request.data.get("subject", "").strip()
        body = request.data.get("body", "").strip()

        if not body:
            return Response({"error": "Email body is required."}, status=400)
        if not subject:
            subject = "Message from your Counselor – HelloIvy"

        sender = User.objects.get(id=self.user_dto.id)
        sender_name = f"{sender.first_name} {sender.last_name}".strip() or sender.email

        html_content = (
            f"<p>Hi {student.first_name or 'there'},</p>"
            f"<p>{body.replace(chr(10), '<br>')}</p>"
            f"<br><p>— {sender_name}<br>"
            f"<span style='color:#888;font-size:12px;'>{sender.email}</span></p>"
        )

        from utils.email import send_email
        email_sent = False
        try:
            send_email(to=student.email, subject=subject, html=html_content)
            email_sent = True
        except Exception as e:
            print(f"[COUNSELOR EMAIL] Failed to send email to {student.email}: {e}")

        return Response({
            "message": "Email sent successfully" if email_sent else "Email queued (SendGrid not configured locally)",
            "sent_to": student.email,
            "email_sent": email_sent,
        }, status=200)


class StudentSendCounselorEmailView(UserDTOView):
    """Student sends an email to their assigned counselor (school admin)."""

    @extend_schema(request=None, responses={200: "Email sent."})
    def post(self, request: Request) -> Response:
        student = User.objects.get(id=self.user_dto.id)

        if not student.school_id:
            return Response({
                "error": "You are not associated with any school. No counselor found."
            }, status=400)

        # Find the school admin (counselor) for this student's school
        counselor = User.objects.filter(
            school_id=student.school_id,
            role=UserRole.SCHOOLADMIN,
            is_active=True,
        ).first()

        if not counselor:
            return Response({
                "error": "No counselor found for your school. Please contact support."
            }, status=400)

        subject = request.data.get("subject", "").strip()
        body = request.data.get("body", "").strip()

        if not body:
            return Response({"error": "Email body is required."}, status=400)
        if not subject:
            subject = "Message from Student – HelloIvy"

        student_name = f"{student.first_name} {student.last_name}".strip() or student.email

        html_content = (
            f"<p>Hi {counselor.first_name or 'there'},</p>"
            f"<p>You have a new message from <strong>{student_name}</strong> ({student.email}):</p>"
            f"<p>{body.replace(chr(10), '<br>')}</p>"
            f"<br><p>— {student_name}<br>"
            f"<span style='color:#888;font-size:12px;'>{student.email}</span></p>"
        )

        from utils.email import send_email
        email_sent = False
        try:
            send_email(to=counselor.email, subject=subject, html=html_content)
            email_sent = True
        except Exception as e:
            print(f"[STUDENT EMAIL] Failed to send email to {counselor.email}: {e}")

        counselor_name = f"{counselor.first_name} {counselor.last_name}".strip() or counselor.email
        return Response({
            "message": "Email sent successfully" if email_sent else "Email queued (SendGrid not configured locally)",
            "sent_to": counselor.email,
            "counselor_name": counselor_name,
            "email_sent": email_sent,
        }, status=200)

    def get(self, request: Request) -> Response:
        """Return counselor info for the student's school."""
        student = User.objects.get(id=self.user_dto.id)

        if not student.school_id:
            return Response({"counselor": None}, status=200)

        counselor = User.objects.filter(
            school_id=student.school_id,
            role=UserRole.SCHOOLADMIN,
            is_active=True,
        ).first()

        if not counselor:
            return Response({"counselor": None}, status=200)

        return Response({
            "counselor": {
                "name": f"{counselor.first_name} {counselor.last_name}".strip() or counselor.email,
                "email": counselor.email,
            }
        }, status=200)
