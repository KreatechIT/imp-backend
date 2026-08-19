from django.urls import include, path

from apps.earnings import routers

urlpatterns = [
    path("", include(routers.earnings_router.urls)),
]
