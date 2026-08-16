from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenVerifyView

from apps.login import views

urlpatterns = [
    path("admin-access-token/", views.AdminAccessTokenView.as_view(), name="admin-access-token"),
    path("member-access-token/", views.MemberAccessTokenView.as_view(), name="member-access-token"),
    path("refresh-token/", views.CustomRefreshTokenView.as_view(), name="token-refresh"),
    path("verify-token/", TokenVerifyView.as_view(), name="token-verify"),
    path("logout/", TokenBlacklistView.as_view(), name="token-blacklist"),
]
