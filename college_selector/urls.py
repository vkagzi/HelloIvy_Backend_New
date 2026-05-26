from django.urls import path
from .views import (
    CollegeSelectorDegreeOptionsView,
    CollegeSelectorSessionCreateView,
    CollegeSelectorSessionListView,
    CollegeSelectorSessionDetailView,
    CollegeSelectorSavePreferencesView,
    CollegeSelectorSendMessageView,
    CollegeSelectorMessageHistoryView,
    CollegeSelectorSessionEndView,
    CollegeSelectorSessionPauseView,
    CollegeSelectorGenerateRecommendationsView,
    CollegeSelectorGetRecommendationsView,
    CollegeSelectorTranscribeAudioView,
    CollegeSelectorGenerateSpeechView,
    CollegeSelectorTranscriptView,
    CollegeSelectorTestScoresView,
    CollegeSelectorSessionDebugView,
    CollegeSelectorHealthCheckView,
)

app_name = 'college_selector'

urlpatterns = [
    # Health check
    path('health/', CollegeSelectorHealthCheckView.as_view(), name='health_check'),

    # Static options
    path('degree-options/', CollegeSelectorDegreeOptionsView.as_view(), name='degree_options'),

    # Session management
    path('', CollegeSelectorSessionCreateView.as_view(), name='session_create'),
    path('list/', CollegeSelectorSessionListView.as_view(), name='session_list'),

    # Test Scores (reads/writes to profile) — must be before <str:session_id> catch-all
    path('test-scores/', CollegeSelectorTestScoresView.as_view(), name='test_scores'),

    path('<str:session_id>/', CollegeSelectorSessionDetailView.as_view(), name='session_detail'),
    path('<str:session_id>/end/', CollegeSelectorSessionEndView.as_view(), name='session_end'),
    path('<str:session_id>/pause/', CollegeSelectorSessionPauseView.as_view(), name='session_pause'),

    # Preferences (static questionnaire)
    path('<str:session_id>/preferences/', CollegeSelectorSavePreferencesView.as_view(), name='preferences'),

    # Messages / Conversation
    path('<str:session_id>/messages/', CollegeSelectorSendMessageView.as_view(), name='message_create'),
    path('<str:session_id>/messages/history/', CollegeSelectorMessageHistoryView.as_view(), name='message_history'),

    # Recommendations
    path('<str:session_id>/recommendations/generate/', CollegeSelectorGenerateRecommendationsView.as_view(), name='recommendations_generate'),
    path('<str:session_id>/recommendations/', CollegeSelectorGetRecommendationsView.as_view(), name='recommendations_get'),

    # Debug
    path('<str:session_id>/debug/', CollegeSelectorSessionDebugView.as_view(), name='session_debug'),

    # Transcript
    path('<str:session_id>/transcript/', CollegeSelectorTranscriptView.as_view(), name='transcript'),

    # Audio (Whisper STT & TTS)
    path('audio/transcribe/', CollegeSelectorTranscribeAudioView.as_view(), name='audio_transcribe'),
    path('audio/speech/', CollegeSelectorGenerateSpeechView.as_view(), name='audio_speech'),
]
