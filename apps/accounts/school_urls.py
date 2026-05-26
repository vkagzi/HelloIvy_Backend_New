from django.urls import path
from .school_views import (
    SchoolListCreateView,
    SchoolDetailView,
    SchoolSubscriptionView,
    SchoolSubscriptionDetailView,
    SchoolStudentsView,
    SchoolStudentRemoveView,
    SchoolAdminsView,
    SchoolAdminRemoveView,
    SchoolOpsAdminsView,
    SchoolOpsAdminDetailView,
    SchoolOpsAdminRemoveView,
)
from .dashboard_views import SchoolDashboardView
from .notification_views import (
    SchoolNotificationSendView,
    StudentNotificationListView,
    StudentNotificationReadView,
    StudentNotificationUnreadCountView,
)
from .deadline_views import (
    SchoolDeadlineListCreateView,
    SchoolDeadlineDeleteView,
    StudentDeadlineListView,
)
from .document_views import (
    SchoolDocumentListCreateView,
    StudentDocumentListView,
)

school_urlpatterns = [
    path("", SchoolListCreateView.as_view()),
    path("<int:school_id>/", SchoolDetailView.as_view()),
    path("<int:school_id>/subscriptions/", SchoolSubscriptionView.as_view()),
    path("<int:school_id>/subscriptions/<int:sub_id>/", SchoolSubscriptionDetailView.as_view()),
    path("<int:school_id>/students/", SchoolStudentsView.as_view()),
    path(
        "<int:school_id>/students/<int:user_id>/",
        SchoolStudentRemoveView.as_view(),
    ),
    path("<int:school_id>/admins/", SchoolAdminsView.as_view()),
    path(
        "<int:school_id>/admins/<int:user_id>/",
        SchoolAdminRemoveView.as_view(),
    ),
    path("<int:school_id>/ops-admins/", SchoolOpsAdminsView.as_view()),
    path(
        "<int:school_id>/ops-admins/<int:user_id>/",
        SchoolOpsAdminRemoveView.as_view(),
    ),
    path("operations-admin/<int:user_id>/", SchoolOpsAdminDetailView.as_view()),
    path("<int:school_id>/dashboard/", SchoolDashboardView.as_view()),
    path("<int:school_id>/notifications/", SchoolNotificationSendView.as_view()),
    path("<int:school_id>/deadlines/", SchoolDeadlineListCreateView.as_view()),
    path(
        "<int:school_id>/deadlines/<int:deadline_id>/",
        SchoolDeadlineDeleteView.as_view(),
    ),
    path("<int:school_id>/documents/", SchoolDocumentListCreateView.as_view()),
]

notification_urlpatterns = [
    path("", StudentNotificationListView.as_view()),
    path("<int:notification_id>/read/", StudentNotificationReadView.as_view()),
    path("unread-count/", StudentNotificationUnreadCountView.as_view()),
]

deadline_urlpatterns = [
    path("", StudentDeadlineListView.as_view()),
]

document_urlpatterns = [
    path("", StudentDocumentListView.as_view()),
]
