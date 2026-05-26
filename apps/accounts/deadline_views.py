from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema
from django.db import models

from utils.user_dto_view import UserDTOView
from .roles import UserRole
from .models import Deadline, School, User
from .serializers import DeadlineSerializer, DeadlineCreateSerializer


class SchoolDeadlineListCreateView(UserDTOView):
    """List or create deadlines for a school."""

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: DeadlineSerializer(many=True)})
    def get(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        deadlines = Deadline.objects.filter(school_id=school_id).order_by("date", "time")
        return Response(
            {"deadlines": DeadlineSerializer(deadlines, many=True).data},
            status=200,
        )

    @extend_schema(request=DeadlineCreateSerializer, responses={201: DeadlineSerializer})
    def post(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        serializer = DeadlineCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        creator = User.objects.get(id=self.user_dto.id)
        deadline = Deadline.objects.create(
            school=school,
            title=serializer.validated_data["title"],
            date=serializer.validated_data["date"],
            time=serializer.validated_data.get("time"),
            target_grade=serializer.validated_data.get("target_grade", ""),
            created_by=creator,
        )
        return Response(DeadlineSerializer(deadline).data, status=201)


class SchoolDeadlineDeleteView(UserDTOView):
    """Delete a deadline."""

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    def delete(self, request: Request, school_id: int, deadline_id: int) -> Response:
        self._check_access(school_id)
        try:
            deadline = Deadline.objects.get(id=deadline_id, school_id=school_id)
        except Deadline.DoesNotExist:
            return Response({"error": "Deadline not found"}, status=404)
        deadline.delete()
        return Response({"message": "Deadline deleted"}, status=200)


class StudentDeadlineListView(UserDTOView):
    """List deadlines for the authenticated student's school."""

    def get(self, request: Request) -> Response:
        if not self.user_dto.school_id:
            return Response({"deadlines": []}, status=200)

        deadlines = Deadline.objects.filter(
            school_id=self.user_dto.school_id
        ).order_by("date", "time")

        # Optionally filter by student's grade
        grade = request.query_params.get("grade")
        if grade:
            deadlines = deadlines.filter(
                models.Q(target_grade="") | models.Q(target_grade__isnull=True) | models.Q(target_grade=grade)
            )
        else:
            # Show all deadlines (grade-specific + school-wide)
            pass

        return Response(
            {"deadlines": DeadlineSerializer(deadlines, many=True).data},
            status=200,
        )
