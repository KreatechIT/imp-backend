from django.urls import include, path

from apps.front_view import routers

urlpatterns = [
    path("", include(routers.front_view_router.urls)),
]
