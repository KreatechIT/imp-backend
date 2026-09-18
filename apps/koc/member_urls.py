from django.urls import include, path

from apps.koc import routers

urlpatterns = [
    path("", include(routers.member_router.urls)),
]
