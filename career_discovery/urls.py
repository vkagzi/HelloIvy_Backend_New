from django.urls import path
from .views import (
    CareerDomainsListView,
    CareerSessionCreateView,
    CareerSessionListView,
    CareerSessionDetailView,
    CareerMessageCreateView,
    CareerMessageStreamView,
    CareerMessageHistoryView,
    CareerSessionEndView,
    CareerSessionPauseView,
    CareerRecommendationsGenerateView,
    CareerRecommendationsGetView,
    CareerHealthCheckView,
    CareerSessionDebugView,
)

app_name = 'career_discovery'

urlpatterns = [
    # Health check
    path('health/', CareerHealthCheckView.as_view(), name='health_check'),
    
    # Domains
    path('domains/', CareerDomainsListView.as_view(), name='domains_list'),
    
    # Session management
    path('', CareerSessionCreateView.as_view(), name='session_create'),
    path('list/', CareerSessionListView.as_view(), name='session_list'),
    path('<str:session_id>/', CareerSessionDetailView.as_view(), name='session_detail'),
    path('<str:session_id>/end/', CareerSessionEndView.as_view(), name='session_end'),
    path('<str:session_id>/pause/', CareerSessionPauseView.as_view(), name='session_pause'),
    path('<str:session_id>/debug/', CareerSessionDebugView.as_view(), name='session_debug'),
    
    # Messages / Conversation
    path('<str:session_id>/messages/', CareerMessageCreateView.as_view(), name='message_create'),
    path('<str:session_id>/messages/stream/', CareerMessageStreamView.as_view(), name='message_stream'),
    path('<str:session_id>/messages/history/', CareerMessageHistoryView.as_view(), name='message_history'),
    
    # Recommendations
    path('<str:session_id>/recommendations/generate/', CareerRecommendationsGenerateView.as_view(), name='recommendations_generate'),
    path('<str:session_id>/recommendations/', CareerRecommendationsGetView.as_view(), name='recommendations_get'),
]
