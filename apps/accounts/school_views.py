import os
import secrets
import uuid

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from azure.storage.blob import BlobServiceClient, ContentSettings
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema

from utils.user_dto_view import UserDTOView
from .roles import UserRole
from .models import School, SchoolModuleSubscription, User, UserModuleSubscription, GradeModuleAutoAssignment
from .permissions import IsSuperOrOperationAdmin, SchoolScopedPermission
from .serializers import (
    SchoolSerializer,
    SchoolCreateUpdateSerializer,
    SchoolModuleSubscriptionSerializer,
)

ALLOWED_LOGO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
MAX_LOGO_SIZE = 5 * 1024 * 1024  # 5 MB

CONTENT_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def save_school_logo(file) -> str:
    """Validate and upload a logo file to Azure Blob Storage, returning its public URL."""
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        raise ValueError(f"Invalid file type '{ext}'. Allowed: {', '.join(ALLOWED_LOGO_EXTENSIONS)}")
    if file.size > MAX_LOGO_SIZE:
        raise ValueError("Logo file must be under 5 MB")

    connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
    container_name = settings.AZURE_STORAGE_CONTAINER_NAME

    blob_name = f"school-logos/{uuid.uuid4().hex}{ext}"
    content_settings = ContentSettings(content_type=CONTENT_TYPE_MAP.get(ext, "application/octet-stream"))

    blob_service = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)
    blob_client.upload_blob(file, overwrite=True, content_settings=content_settings)

    return blob_client.url


class SchoolListCreateView(UserDTOView):
    """List all schools or create a new school."""

    parser_classes = [MultiPartParser, JSONParser]

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: SchoolSerializer(many=True)})
    def get(self, request: Request) -> Response:
        self._require_admin()
        schools = School.objects.all().order_by("-created_at")
        serializer = SchoolSerializer(schools, many=True)
        return Response({"schools": serializer.data}, status=200)

    @extend_schema(request=SchoolCreateUpdateSerializer, responses={201: SchoolSerializer})
    def post(self, request: Request) -> Response:
        self._require_admin()
        logo_file = request.FILES.get("logo_file")
        logo_url = None
        if logo_file:
            try:
                logo_url = save_school_logo(logo_file)
            except ValueError as exc:
                return Response({"logo_file": [str(exc)]}, status=400)

        # Build clean data dict excluding file fields
        data = {}
        for key, value in request.data.items():
            if key != "logo_file":
                data[key] = value
        
        if logo_url:
            data["logo_url"] = logo_url

        serializer = SchoolCreateUpdateSerializer(data=data)
        if serializer.is_valid():
            school = serializer.save()
            return Response(SchoolSerializer(school).data, status=201)
        return Response(serializer.errors, status=400)


class SchoolDetailView(UserDTOView):
    """Retrieve, update, or deactivate a school."""

    parser_classes = [MultiPartParser, JSONParser]

    def _get_school(self, school_id: int) -> School:
        try:
            return School.objects.get(id=school_id)
        except School.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("School not found")

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: SchoolSerializer})
    def get(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        school = self._get_school(school_id)
        return Response(SchoolSerializer(school).data, status=200)

    @extend_schema(request=SchoolCreateUpdateSerializer, responses={200: SchoolSerializer})
    def put(self, request: Request, school_id: int) -> Response:
        is_school_admin = self.user_dto.role == UserRole.SCHOOLADMIN
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN) and not is_school_admin:
            raise PermissionDenied(detail="Admin access required")
        if is_school_admin and self.user_dto.school_id != school_id:
            raise PermissionDenied(detail="Access denied to this school")
        school = self._get_school(school_id)

        # Handle logo file upload if provided
        logo_file = request.FILES.get("logo_file")
        if logo_file:
            try:
                logo_url = save_school_logo(logo_file)
                data = {k: v for k, v in request.data.items() if k != "logo_file"}
                data["logo_url"] = logo_url
            except ValueError as exc:
                return Response({"logo_file": [str(exc)]}, status=400)
        else:
            data = {k: v for k, v in request.data.items() if k != "logo_file"}

        # School admins cannot change is_active
        if is_school_admin:
            data.pop("is_active", None)

        serializer = SchoolCreateUpdateSerializer(school, data=data, partial=True)
        if serializer.is_valid():
            school = serializer.save()
            return Response(SchoolSerializer(school).data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request: Request, school_id: int) -> Response:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")
        school = self._get_school(school_id)
        school.is_active = False
        school.save(update_fields=["is_active", "updated_at"])
        return Response({"message": "School deactivated"}, status=200)


class SchoolSubscriptionView(UserDTOView):
    """Manage module subscriptions for a school."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: SchoolModuleSubscriptionSerializer(many=True)})
    def get(self, request: Request, school_id: int) -> Response:
        self._require_admin()
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)
        subs = school.subscriptions.all().order_by("module_name")
        return Response(
            {"subscriptions": SchoolModuleSubscriptionSerializer(subs, many=True).data},
            status=200,
        )

    @extend_schema(request=SchoolModuleSubscriptionSerializer)
    def post(self, request: Request, school_id: int) -> Response:
        self._require_admin()
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)
        serializer = SchoolModuleSubscriptionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(school=school)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class SchoolSubscriptionDetailView(UserDTOView):
    """Edit or delete a single school module subscription (superadmin / operationadmin)."""

    def _require_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    def patch(self, request: Request, school_id: int, sub_id: int) -> Response:
        self._require_admin()
        try:
            sub = SchoolModuleSubscription.objects.get(id=sub_id, school_id=school_id)
        except SchoolModuleSubscription.DoesNotExist:
            return Response({"error": "Subscription not found"}, status=404)
        serializer = SchoolModuleSubscriptionSerializer(sub, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)

    def delete(self, request: Request, school_id: int, sub_id: int) -> Response:
        self._require_admin()
        try:
            sub = SchoolModuleSubscription.objects.get(id=sub_id, school_id=school_id)
        except SchoolModuleSubscription.DoesNotExist:
            return Response({"error": "Subscription not found"}, status=404)
        sub.delete()
        return Response(status=204)


class SchoolStudentsView(UserDTOView):
    """List / add / remove students for a school."""

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: "List of students."})
    def get(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        students = User.objects.filter(school=school, role=UserRole.STUDENT).order_by("-created_at")

        # Grade filter — queries profile JSON
        grade = request.query_params.get("grade")
        if grade:
            from apps.profiles.models import UserProfile
            student_ids = students.values_list("id", flat=True)
            profiles = UserProfile.objects.filter(user_id__in=student_ids)
            matching_ids = []
            for p in profiles:
                profile_data = p.profile_json.get("profile", p.profile_json)
                edu = profile_data.get("educational", {})
                student_grade = str(edu.get("grade", ""))
                if student_grade == str(grade):
                    matching_ids.append(p.user_id)
            students = students.filter(id__in=matching_ids)

        # Module filter — any active subscription
        module_filter = request.query_params.get("module")
        if module_filter:
            students = students.filter(
                id__in=UserModuleSubscription.objects.filter(
                    module_name=module_filter, is_active=True
                ).values_list("user_id", flat=True)
            )

        # Check if grouping by grade is requested
        group_by = request.query_params.get("group_by")
        if group_by == "grade":
            # Fetch all students with profiles for grouping
            from apps.profiles.models import UserProfile
            student_ids = list(students.values_list("id", flat=True))
            profiles_map = {
                p.user_id: p.profile_json
                for p in UserProfile.objects.filter(user_id__in=student_ids)
            }

            # Fetch all active subscriptions for these students (could be school-assigned or self-purchased)
            assignments_qs = UserModuleSubscription.objects.filter(
                user_id__in=student_ids,
                is_active=True,
            ).values("user_id", "id", "module_name", "reminder_last_sent_at", "reminder_count")
            assignments_map: dict[int, list[dict]] = {}
            for a in assignments_qs:
                assignments_map.setdefault(a["user_id"], []).append({
                    "id": a["id"],
                    "module_name": a["module_name"],
                    "reminder_last_sent_at": a["reminder_last_sent_at"].isoformat() if a["reminder_last_sent_at"] else None,
                    "reminder_count": a["reminder_count"],
                })

            # Fetch auto-assign rules for this school
            auto_rules = list(
                GradeModuleAutoAssignment.objects.filter(
                    school_id=school_id, is_active=True
                ).values_list("grade_level", flat=True).distinct()
            )

            # Build complete student data
            all_students_data = []
            for s in students:
                student_assignments = assignments_map.get(s.id, [])
                
                # Check usage for each assigned module
                from .services import get_module_usage_count
                for a in student_assignments:
                    a["used"] = get_module_usage_count(a["module_name"], [s.id]) > 0

                profile_json = profiles_map.get(s.id, {})
                profile_inner = profile_json.get("profile", profile_json)
                edu = profile_inner.get("educational", {})
                all_students_data.append(
                    {
                        "id": s.id,
                        "email": s.email,
                        "first_name": s.first_name,
                        "last_name": s.last_name,
                        "grade": edu.get("grade", "") or s.grade_level or "",
                        "section": edu.get("section", ""),
                        "board": edu.get("board", ""),
                        "is_active": s.is_active,
                        "last_login": s.last_login.isoformat() if s.last_login else None,
                        "created_at": s.created_at.isoformat(),
                        "assigned_modules": student_assignments,
                    }
                )

            # Group students by grade
            grouped_students = {}
            for student in all_students_data:
                grade_key = student.get("grade") or "No Grade"
                if grade_key not in grouped_students:
                    grouped_students[grade_key] = []
                grouped_students[grade_key].append(student)

            return Response(
                {
                    "grouped_students": grouped_students,
                    "total": len(all_students_data),
                    "groups": list(grouped_students.keys()),
                    "auto_assign_grades": auto_rules,
                },
                status=200,
            )

        # Pagination for non-grouped results
        page = int(request.query_params.get("page", 1))
        page_size = min(int(request.query_params.get("page_size", 20)), 100)
        total = students.count()
        start = (page - 1) * page_size
        page_students = students[start : start + page_size]

        # Build response with profile data
        from apps.profiles.models import UserProfile
        student_ids = [s.id for s in page_students]
        profiles_map = {
            p.user_id: p.profile_json
            for p in UserProfile.objects.filter(user_id__in=student_ids)
        }

        students_data = []
        for s in page_students:
            profile_json = profiles_map.get(s.id, {})
            profile_inner = profile_json.get("profile", profile_json)
            personal = profile_inner.get("personalDetails", {})
            edu = profile_inner.get("educational", {})
            students_data.append(
                {
                    "id": s.id,
                    "email": s.email,
                    "first_name": s.first_name,
                    "last_name": s.last_name,
                    "grade": edu.get("grade", ""),
                    "section": edu.get("section", ""),
                    "board": edu.get("board", ""),
                    "is_active": s.is_active,
                    "last_login": s.last_login.isoformat() if s.last_login else None,
                    "created_at": s.created_at.isoformat(),
                }
            )

        return Response(
            {
                "students": students_data,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            status=200,
        )

    @extend_schema(request=None, responses={200: "Student added to school."})
    def post(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        email = request.data.get("email")
        user_id = request.data.get("user_id")

        if email:
            user = User.objects.filter(email=email, role=UserRole.STUDENT).first()
        elif user_id:
            user = User.objects.filter(id=user_id, role=UserRole.STUDENT).first()
        else:
            return Response({"error": "Provide email or user_id"}, status=400)

        if not user:
            return Response({"error": "Student not found"}, status=404)

        user.school = school
        user.save(update_fields=["school", "updated_at"])

        # Auto-assign modules based on grade rules
        from .services import auto_assign_modules_for_student
        auto_assigned = auto_assign_modules_for_student(user)

        response_data = {"message": f"Student {user.email} added to {school.name}"}
        if auto_assigned:
            response_data["auto_assigned_modules"] = auto_assigned
        return Response(response_data, status=200)


class SchoolAdminsView(UserDTOView):
    """List / add school admin users for a school."""

    def _require_super_or_op_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: "List of school admins."})
    def get(self, request: Request, school_id: int) -> Response:
        self._require_super_or_op_admin()
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        admins = User.objects.filter(school=school, role=UserRole.SCHOOLADMIN).order_by("-created_at")
        admins_data = [
            {
                "id": a.id,
                "email": a.email,
                "is_active": a.is_active,
                "last_login": a.last_login.isoformat() if a.last_login else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in admins
        ]
        return Response({"admins": admins_data, "total": len(admins_data)}, status=200)

    @extend_schema(request=None, responses={200: "School admin added."})
    def post(self, request: Request, school_id: int) -> Response:
        self._require_super_or_op_admin()
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        email = request.data.get("email", "").strip()
        if not email:
            return Response({"error": "Email is required"}, status=400)

        send_password_email = request.data.get("send_password_email", True)

        user = User.objects.filter(email=email).first()
        if user:
            if user.role == UserRole.SCHOOLADMIN and user.school_id == school_id:
                return Response({"error": "User is already a school admin for this school"}, status=400)
            user.role = UserRole.SCHOOLADMIN
            user.school = school
            user.is_active = True
            user.save(update_fields=["role", "school", "is_active", "updated_at"])
        else:
            from utils.email import send_school_admin_welcome_email
            temp_password = secrets.token_urlsafe(10)
            user = User(email=email, role=UserRole.SCHOOLADMIN, school=school, is_active=True,
                        force_password_change=True)
            user.set_password(temp_password)
            user.save()
            if send_password_email:
                try:
                    send_school_admin_welcome_email(user.email, temp_password, school.name)
                except Exception as e:
                    print(f"[SCHOOL ADMIN CREATE] Email failed for {user.email}: {e}")

        return Response(
            {"message": f"{email} added as school admin for {school.name}"},
            status=200,
        )


class SchoolAdminRemoveView(UserDTOView):
    """Remove a school admin from a school."""

    def _require_super_or_op_admin(self) -> None:
        if self.user_dto.role not in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            raise PermissionDenied(detail="Admin access required")

    def delete(self, request: Request, school_id: int, user_id: int) -> Response:
        self._require_super_or_op_admin()
        try:
            user = User.objects.get(id=user_id, school_id=school_id, role=UserRole.SCHOOLADMIN)
        except User.DoesNotExist:
            return Response({"error": "School admin not found in this school"}, status=404)
        user.school = None
        user.role = UserRole.STUDENT
        user.save(update_fields=["school", "role", "updated_at"])
        return Response({"message": "School admin removed"}, status=200)


class SchoolStudentRemoveView(UserDTOView):
    """Remove a student from a school."""

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    def delete(self, request: Request, school_id: int, user_id: int) -> Response:
        self._check_access(school_id)
        try:
            user = User.objects.get(id=user_id, school_id=school_id, role=UserRole.STUDENT)
        except User.DoesNotExist:
            return Response({"error": "Student not found in this school"}, status=404)
        user.school = None
        user.save(update_fields=["school", "updated_at"])
        return Response({"message": "Student removed from school"}, status=200)


class SchoolOpsAdminsView(UserDTOView):
    """List / add school ops admin users for a school."""

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: "List of school ops admins."})
    def get(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        ops_admins = User.objects.filter(school=school, role=UserRole.SCHOOLOPSADMIN).order_by("-created_at")
        ops_admins_data = [
            {
                "id": a.id,
                "email": a.email,
                "first_name": a.first_name,
                "last_name": a.last_name,
                "is_active": a.is_active,
                "last_login": a.last_login.isoformat() if a.last_login else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in ops_admins
        ]
        return Response({"ops_admins": ops_admins_data, "total": len(ops_admins_data)}, status=200)

    @extend_schema(request=None, responses={200: "School ops admin added."})
    def post(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        email = request.data.get("email", "").strip()
        if not email:
            return Response({"error": "Email is required"}, status=400)

        first_name = request.data.get("first_name", "").strip()
        last_name = request.data.get("last_name", "").strip()

        send_password_email = request.data.get("send_password_email", True)

        user = User.objects.filter(email=email).first()
        if user:
            if user.role == UserRole.SCHOOLOPSADMIN and user.school_id == school_id:
                return Response({"error": "User is already a school ops admin for this school"}, status=400)
            user.role = UserRole.SCHOOLOPSADMIN
            user.school = school
            user.is_active = True
            update_fields = ["role", "school", "is_active", "updated_at"]
            if first_name:
                user.first_name = first_name
                update_fields.append("first_name")
            if last_name:
                user.last_name = last_name
                update_fields.append("last_name")
            user.save(update_fields=update_fields)
        else:
            from utils.email import send_temp_password_email
            temp_password = secrets.token_urlsafe(10)
            user = User(email=email, role=UserRole.SCHOOLOPSADMIN, school=school, is_active=True,
                        first_name=first_name, last_name=last_name, force_password_change=True)
            user.set_password(temp_password)
            user.save()
            if send_password_email:
                try:
                    student_name = f"{user.first_name} {user.last_name}".strip()
                    send_temp_password_email(user.email, temp_password, student_name=student_name)
                except Exception as e:
                    print(f"[SCHOOL OPS ADMIN CREATE] Email failed for {user.email}: {e}")

        return Response(
            {"message": f"{email} added as school ops admin for {school.name}"},
            status=200,
        )


class SchoolOpsAdminDetailView(UserDTOView):
    """Get, update, or change password for a specific operations admin."""

    def _check_access(self, user: User) -> None:
        """Check if current user can access/manage this ops admin."""
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if user.school_id and self.user_dto.school_id == user.school_id:
                return
            raise PermissionDenied(detail="Access denied to this operations admin")
        raise PermissionDenied(detail="Admin access required")

    def _get_ops_admin_data(self, user: User) -> dict:
        """Return formatted ops admin data."""
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat(),
            "school_id": user.school_id,
            "school_name": user.school.name if user.school else None,
        }

    @extend_schema(responses={200: "Operations admin details."})
    def get(self, request: Request, user_id: int) -> Response:
        try:
            user = User.objects.get(id=user_id, role=UserRole.SCHOOLOPSADMIN)
        except User.DoesNotExist:
            return Response({"error": "Operations admin not found"}, status=404)
        
        self._check_access(user)
        return Response(self._get_ops_admin_data(user), status=200)

    @extend_schema(request=None, responses={200: "Operations admin updated."})
    def put(self, request: Request, user_id: int) -> Response:
        try:
            user = User.objects.get(id=user_id, role=UserRole.SCHOOLOPSADMIN)
        except User.DoesNotExist:
            return Response({"error": "Operations admin not found"}, status=404)
        
        self._check_access(user)
        
        # Allow updating is_active status
        if "is_active" in request.data:
            user.is_active = request.data.get("is_active", user.is_active)
            user.save(update_fields=["is_active", "updated_at"])
        
        return Response(self._get_ops_admin_data(user), status=200)

    @extend_schema(request=None, responses={200: "Operations admin name updated."})
    def patch(self, request: Request, user_id: int) -> Response:
        """Update first_name and last_name for operations admin."""
        try:
            user = User.objects.get(id=user_id, role=UserRole.SCHOOLOPSADMIN)
        except User.DoesNotExist:
            return Response({"error": "Operations admin not found"}, status=404)

        self._check_access(user)

        data = request.data
        if "first_name" in data:
            user.first_name = data["first_name"] or ""
        if "last_name" in data:
            user.last_name = data["last_name"] or ""
        user.save(update_fields=["first_name", "last_name", "updated_at"])

        return Response(self._get_ops_admin_data(user), status=200)

    @extend_schema(request=None, responses={200: "Password changed successfully."})
    def post(self, request: Request, user_id: int) -> Response:
        """Change password for operations admin."""
        try:
            user = User.objects.get(id=user_id, role=UserRole.SCHOOLOPSADMIN)
        except User.DoesNotExist:
            return Response({"error": "Operations admin not found"}, status=404)
        
        self._check_access(user)
        
        new_password = request.data.get("new_password", "").strip()
        if not new_password or len(new_password) < 6:
            return Response(
                {"error": "Password must be at least 6 characters long"},
                status=400
            )
        
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        
        return Response(
            {
                "message": "Password changed successfully",
                "user_id": user.id,
                "email": user.email,
            },
            status=200
        )


class SchoolOpsAdminRemoveView(UserDTOView):
    """Remove a school ops admin from a school."""

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role == UserRole.SCHOOLADMIN:
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    def delete(self, request: Request, school_id: int, user_id: int) -> Response:
        self._check_access(school_id)
        try:
            user = User.objects.get(id=user_id, school_id=school_id, role=UserRole.SCHOOLOPSADMIN)
        except User.DoesNotExist:
            return Response({"error": "School ops admin not found in this school"}, status=404)
        user.school = None
        user.role = UserRole.STUDENT
        user.save(update_fields=["school", "role", "updated_at"])
        return Response({"message": "School ops admin removed"}, status=200)
