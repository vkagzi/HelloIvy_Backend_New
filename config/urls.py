"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .health_check import HealthCheckView
from utils.tts_views import GenerateSpeechView
from apps.accounts.school_urls import (
    school_urlpatterns,
    notification_urlpatterns,
    deadline_urlpatterns,
    document_urlpatterns,
)
from apps.accounts.payment_views import (
    UserPaymentListCreateView,
    UserPaymentDetailView,
    SchoolPaymentListCreateView,
    SchoolPaymentDetailView,
    AdminPaymentRefreshView,
    ModulePricingListCreateView,
    ModulePricingDetailView,
)


urlpatterns = [
    path("", HealthCheckView.as_view(), name="health-check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Optional UI:
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/profiles/", include("apps.profiles.urls")),
    path("api/career-discovery/", include("career_discovery.urls")),
    path("api/domain-discovery/", include("domain_discovery.urls")),
    path("api/college-selector/", include("college_selector.urls")),
    path("api/locations/", include("apps.locations.urls")),
    path("api/tts/", GenerateSpeechView.as_view(), name="tts"),
    # School admin endpoints
    path("api/schools/", include(school_urlpatterns)),
    path("api/notifications/", include(notification_urlpatterns)),
    path("api/deadlines/", include(deadline_urlpatterns)),
    path("api/documents/", include(document_urlpatterns)),
    # Payment endpoints
    path("api/payments/b2c/", UserPaymentListCreateView.as_view()),
    path("api/payments/b2c/<int:payment_id>/", UserPaymentDetailView.as_view()),
    path("api/payments/schools/", SchoolPaymentListCreateView.as_view()),
    path("api/payments/schools/<int:payment_id>/", SchoolPaymentDetailView.as_view()),
    path("api/payments/<str:payment_type>/<int:payment_id>/refresh/", AdminPaymentRefreshView.as_view()),
    # Module pricing management (admin)
    path("api/pricing/", ModulePricingListCreateView.as_view()),
    path("api/pricing/<int:pricing_id>/", ModulePricingDetailView.as_view()),
]
