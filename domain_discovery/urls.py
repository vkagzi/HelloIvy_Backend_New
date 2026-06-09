from django.urls import path
from .views import (
    DomainSessionCreateView,
    DomainSessionListView,
    DomainSessionDetailView,
    DomainMessageCreateView,
    DomainMessageStreamView,
    DomainMessageHistoryView,
    DomainSessionEndView,
    DomainSessionPauseView,
    DomainRecommendationsGenerateView,
    DomainRecommendationsGetView,
    DomainReportGenerateView,
    DomainReportDownloadView,
    DomainResultsSummaryView,
    DomainTranscriptView,
    DomainTranscriptDownloadView,
    DomainTranscribeAudioView,
    DomainGenerateSpeechView,
    DomainHealthCheckView,
    DomainDebugInfoView,
    SubmitModuleReviewView,
    DomainEmailReportView,
)

app_name = 'domain_discovery'

urlpatterns = [
    # Health check
    path('health/', DomainHealthCheckView.as_view(), name='health_check'),
    
    # Feedback
    path("submit-review/", SubmitModuleReviewView.as_view(), name="submit-module-review"),

    # Session management
    path('', DomainSessionCreateView.as_view(), name='session_create'),
    path('list/', DomainSessionListView.as_view(), name='session_list'),
    path('<str:session_id>/', DomainSessionDetailView.as_view(), name='session_detail'),
    path('<str:session_id>/end/', DomainSessionEndView.as_view(), name='session_end'),
    path('<str:session_id>/pause/', DomainSessionPauseView.as_view(), name='session_pause'),
    
    # Messages / Conversation
    path('<str:session_id>/messages/', DomainMessageCreateView.as_view(), name='message_create'),
    path('<str:session_id>/messages/stream/', DomainMessageStreamView.as_view(), name='message_stream'),
    path('<str:session_id>/messages/history/', DomainMessageHistoryView.as_view(), name='message_history'),
    
    # Recommendations
    path('<str:session_id>/recommendations/generate/', DomainRecommendationsGenerateView.as_view(), name='recommendations_generate'),
    path('<str:session_id>/recommendations/', DomainRecommendationsGetView.as_view(), name='recommendations_get'),
    
    # Final Report
    path('<str:session_id>/report/', DomainReportGenerateView.as_view(), name='report_generate'),
    path('<str:session_id>/report/download/', DomainReportDownloadView.as_view(), name='report_download'),
    
    # Results & Transcript (NEW)
    path('<str:session_id>/results/', DomainResultsSummaryView.as_view(), name='results_summary'),
    path('<str:session_id>/transcript/', DomainTranscriptView.as_view(), name='transcript'),
    path('<str:session_id>/transcript/download/', DomainTranscriptDownloadView.as_view(), name='transcript_download'),
    path('<str:session_id>/email-report/', DomainEmailReportView.as_view(), name='email_report'),
    
    # Debug
    path('<str:session_id>/debug/', DomainDebugInfoView.as_view(), name='debug_info'),
    
    # Audio (Whisper STT & TTS)
    path('audio/transcribe/', DomainTranscribeAudioView.as_view(), name='audio_transcribe'),
    path('audio/speech/', DomainGenerateSpeechView.as_view(), name='audio_speech'),
]