from django.urls import include, path

from apps.frames import routers

urlpatterns = [
    path("", include(routers.frame_router.urls)),
]
