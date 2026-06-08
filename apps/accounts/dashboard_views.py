from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema
from django.db.models import Sum, Max
from django.utils import timezone

from utils.user_dto_view import UserDTOView
from .models import School, SchoolModuleSubscription, ModuleName, User
from .services import get_assigned_count


class SchoolDashboardView(UserDTOView):
    """School-scoped dashboard with module and grade-wise statistics."""

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in ("superadmin", "operationadmin"):
            return
        if self.user_dto.role in ("schooladmin", "schoolopsadmin"):
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: "School dashboard statistics."})
    def get(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        students = User.objects.filter(school=school, role="student")
        total_students = students.count()
        active_students = students.filter(is_active=True).count()

        # Module subscriptions — aggregate by module_name
        # Club max_students across active, non-expired subscriptions for same module
        today = timezone.now().date()
        agg = (
            SchoolModuleSubscription.objects.filter(
                school=school, is_active=True, expiry_date__gte=today
            )
            .values("module_name")
            .annotate(
                total_max_students=Sum("max_students"),
                latest_expiry=Max("expiry_date"),
            )
        )
        module_display_map = dict(ModuleName.choices)
        student_ids = list(students.values_list("id", flat=True))
        modules_data = []
        for row in agg:
            using_count = get_module_usage_count(row["module_name"], student_ids)
            modules_data.append(
                {
                    "module_name": row["module_name"],
                    "module_display": module_display_map.get(row["module_name"], row["module_name"]),
                    "students_using": using_count,
                    "max_students": row["total_max_students"],
                    "expiry_date": row["latest_expiry"].isoformat() if row["latest_expiry"] else None,
                    "is_active": True,
                }
            )

        # Grade-wise overview from profile JSON
        grade_overview = self._build_grade_overview(students)

        return Response(
            {
                "school": {
                    "id": school.id,
                    "name": school.name,
                    "logo_url": school.logo_url,
                },
                "total_students": total_students,
                "active_students": active_students,
                "modules": modules_data,
                "grade_overview": grade_overview,
            },
            status=200,
        )

    def _build_grade_overview(self, students) -> list[dict]:  # type: ignore
        from apps.profiles.models import UserProfile

        student_list = list(students)
        student_ids = [s.id for s in student_list]
        profiles_map = {
            p.user_id: p.profile_json
            for p in UserProfile.objects.filter(user_id__in=student_ids)
        }

        # Aggregate by grade — iterate all students (including those without profiles)
        # to match the same logic used by the students list API
        grade_map: dict[str, dict] = {}
        for s in student_list:
            profile_json = profiles_map.get(s.id, {})
            profile_inner = profile_json.get("profile", profile_json)
            edu = profile_inner.get("educational", {})
            grade = str(edu.get("grade", "") or s.grade_level or "No Grade")
            if not grade:
                grade = "No Grade"

            if grade not in grade_map:
                grade_map[grade] = {
                    "grade": grade,
                    "student_count": 0,
                    "student_ids": [],
                }
            grade_map[grade]["student_count"] += 1
            grade_map[grade]["student_ids"].append(s.id)

        # Build final list
        result = []
        for grade, info in sorted(grade_map.items()):
            entry = {
                "grade": info["grade"],
                "student_count": info["student_count"],
            }

            # Module assignment counts (students assigned to modules via school assignment)
            ids = info["student_ids"]
            entry["domain_discovery_count"] = get_assigned_count("domain_discovery", ids)
            entry["career_discovery_count"] = get_assigned_count("career_discovery", ids)
            result.append(entry)

        return result     
