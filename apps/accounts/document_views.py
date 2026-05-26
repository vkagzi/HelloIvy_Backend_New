from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema

from utils.user_dto_view import UserDTOView
from .roles import UserRole
from .models import SharedDocument, School, User
from .serializers import SharedDocumentSerializer


class SchoolDocumentListCreateView(UserDTOView):
    """List or upload documents for a school."""

    def _check_access(self, school_id: int) -> None:
        if self.user_dto.role in (UserRole.SUPERADMIN, UserRole.OPERATIONADMIN):
            return
        if self.user_dto.role == UserRole.SCHOOLADMIN:
            if self.user_dto.school_id != school_id:
                raise PermissionDenied(detail="Access denied to this school")
            return
        raise PermissionDenied(detail="Admin access required")

    @extend_schema(responses={200: SharedDocumentSerializer(many=True)})
    def get(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        docs = SharedDocument.objects.filter(school_id=school_id).order_by("-created_at")
        return Response(
            {"documents": SharedDocumentSerializer(docs, many=True).data},
            status=200,
        )

    def post(self, request: Request, school_id: int) -> Response:
        self._check_access(school_id)
        try:
            school = School.objects.get(id=school_id)
        except School.DoesNotExist:
            return Response({"error": "School not found"}, status=404)

        file_url = request.data.get("file_url")
        file_name = request.data.get("file_name")
        category = request.data.get("category", "")
        note = request.data.get("note", "")
        student_ids = request.data.get("student_ids", [])

        if not file_url or not file_name:
            return Response(
                {"error": "file_url and file_name are required"}, status=400
            )

        uploader = User.objects.get(id=self.user_dto.id)
        doc = SharedDocument.objects.create(
            school=school,
            uploaded_by=uploader,
            file_url=file_url,
            file_name=file_name,
            category=category,
            note=note,
        )

        # Link to selected students
        if student_ids:
            students = User.objects.filter(
                id__in=student_ids, school=school, role=UserRole.STUDENT
            )
            doc.students.set(students)

            # Send email notifications for uploaded documents
            from utils.email import send_email
            for s in students:
                send_email(
                    to=s.email,
                    subject=f"New document shared: {file_name}",
                    html=f"<p>A new document <b>{file_name}</b> has been shared with you by {school.name}.</p>"
                    f"<p>{note}</p>" if note else "",
                )

        return Response(
            {
                "message": "Document uploaded",
                "document": SharedDocumentSerializer(doc).data,
            },
            status=201,
        )


class StudentDocumentListView(UserDTOView):
    """List documents shared with the authenticated student."""

    def get(self, request: Request) -> Response:
        docs = SharedDocument.objects.filter(
            students__id=self.user_dto.id
        ).order_by("-created_at")
        return Response(
            {"documents": SharedDocumentSerializer(docs, many=True).data},
            status=200,
        )
