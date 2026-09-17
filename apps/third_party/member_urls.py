from django.urls import include, path

from . import routers

urlpatterns = [
    path("", include(routers.member_router.urls)),
]
