from django.urls import include, path

from apps.notifications import routers

urlpatterns = [
    path("", include(routers.notification_router.urls)),
]
