from django.urls import include, path

from apps.jobs import routers

urlpatterns = [
    path("", include(routers.member_router.urls)),
]
