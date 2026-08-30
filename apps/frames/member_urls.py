from django.urls import include, path

from apps.frames import routers

urlpatterns = [
    path("", include(routers.member_router.urls)),
]
