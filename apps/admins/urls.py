from django.urls import include, path

from apps.admins import routers

urlpatterns = [
    path("", include(routers.admin_router.urls)),
]
