from django.urls import path
from .views import GetProfileView, UpdateProfileView, ResumeParserView, TranscriptParserView

urlpatterns = [
    path("", GetProfileView.as_view(), name="get-profile"),
    path("update/", UpdateProfileView.as_view(), name="update-profile"),
    path("parse-resume/", ResumeParserView.as_view(), name="parse_resume"),
    path("parse-transcript/", TranscriptParserView.as_view(), name="parse_transcript"),
]
