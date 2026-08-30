from django.urls import include, path

from apps.members import routers, views

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/change-password/", views.ChangePasswordView.as_view(), name="change-password"),
    path("profile/audit-log/", views.LoginAuditView.as_view(), name="audit-log"),
    path("profile/", include(routers.profile_router.urls)),
    path("", include(routers.admin_member_router.urls)),
    path("", include(routers.member_router.urls)),
]
