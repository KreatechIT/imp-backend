from django.urls import include, path

from apps.jobs import routers, views

urlpatterns = [
    path("settings/", views.JobSettingsView.as_view(), name="settings"),
    path("", include(routers.job_router.urls)),
]
