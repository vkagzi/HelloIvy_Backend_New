from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema
from django.utils import timezone

from utils.user_dto_view import UserDTOView
from .roles import UserRole
from .models import Notification, StudentNotification, School, User
from .serializers import NotificationCreateSerializer, NotificationSerializer


class SchoolNotificationSendView(UserDTOView):
    """Send a notification to students in a school (optionally filtered by grade)."""

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role in (UserRole.SCHOOLADMIN, UserRole.SCHOOLOPSADMIN):
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: NotificationSerializer(many=True)})
    def get(self, request: Request, school_id: int) -> Response:
        """List notifications sent for this school."""
        self._check_access(school_id)
        notifications = Notification.objects.filter(school_id=school_id).order_by("-created_at")
        return Response(
            {"notifications": NotificationSerializer(notifications, many=True).data},
            status=200,
        )

    @extend_schema(request=NotificationCreateSerializer)
    def post(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        serializer = NotificationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        sender = User.objects.get(id=self.user_dto.id)
        target_grade = serializer.validated_data.get("target_grade", "")
        message = serializer.validated_data["message"]

        notification = Notification.objects.create(
            school=school,
            sender=sender,
            target_grade=target_grade,
            message=message,
        )

        # Find target students
        students = User.objects.filter(school=school, role=UserRole.STUDENT, is_active=True)
        if target_grade:
            from apps.profiles.models import UserProfile
            student_ids = list(students.values_list("id", flat=True))
            profiles = UserProfile.objects.filter(user_id__in=student_ids)
            matching_ids = []
            for p in profiles:
                profile_data = p.profile_json.get("profile", p.profile_json)
                edu = profile_data.get("educational", {})
                if str(edu.get("grade", "")) == str(target_grade):
                    matching_ids.append(p.user_id)
            students = students.filter(id__in=matching_ids)

        # Create StudentNotification records
        student_notifications = [
            StudentNotification(notification=notification, student=s)
            for s in students
        ]
        StudentNotification.objects.bulk_create(student_notifications)

        # Send email notifications
        from utils.email import send_email
        grade_label = f" (Grade {target_grade})" if target_grade else ""
        subject = f"HelloIvy Notification from {school.name}{grade_label}"
        for s in students:
            send_email(
                to=s.email,
                subject=subject,
                html=f"<p>{message}</p><br><p>— {school.name}</p>",
            )

        return Response(
            {
                "message": f"Notification sent to {students.count()} students",
                "notification_id": notification.id,
            },
            status=201,
        )


class StudentNotificationListView(UserDTOView):
    """List notifications for the authenticated student."""

    @extend_schema(responses={200: "Student notifications."})
    def get(self, request: Request) -> Response:
        page = int(request.query_params.get("page", 1))
        page_size = min(int(request.query_params.get("page_size", 20)), 100)

        qs = StudentNotification.objects.filter(
            student_id=self.user_dto.id
        ).select_related("notification", "notification__sender").order_by(
            "-notification__created_at"
        )
        total = qs.count()
        start = (page - 1) * page_size
        items = qs[start : start + page_size]

        data = [
            {
                "id": sn.id,
                "notification_id": sn.notification_id,
                "message": sn.notification.message,
                "sender_email": sn.notification.sender.email,
                "school_name": sn.notification.school.name if sn.notification.school else None,
                "target_grade": sn.notification.target_grade,
                "is_read": sn.is_read,
                "read_at": sn.read_at.isoformat() if sn.read_at else None,
                "created_at": sn.notification.created_at.isoformat(),
            }
            for sn in items
        ]
        return Response(
            {"notifications": data, "total": total, "page": page, "page_size": page_size},
            status=200,
        )


class StudentNotificationReadView(UserDTOView):
    """Mark a notification as read."""

    def put(self, request: Request, notification_id: int) -> Response:
        try:
            sn = StudentNotification.objects.get(
                id=notification_id, student_id=self.user_dto.id
            )
        except StudentNotification.DoesNotExist:
            return Response({"error": "Notification not found"}, status=404)

        sn.is_read = True
        sn.read_at = timezone.now()
        sn.save(update_fields=["is_read", "read_at"])
        return Response({"message": "Notification marked as read"}, status=200)


class StudentNotificationUnreadCountView(UserDTOView):
    """Get unread notification count for the authenticated user."""

    def get(self, request: Request) -> Response:
        count = StudentNotification.objects.filter(
            student_id=self.user_dto.id, is_read=False
        ).count()
        return Response({"unread_count": count}, status=200)
