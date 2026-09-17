from django.urls import path

from . import views

urlpatterns = [
    path("callback/", views.ThirdPartyOAuthCallbackView.as_view(), name="oauth-callback"),
]
