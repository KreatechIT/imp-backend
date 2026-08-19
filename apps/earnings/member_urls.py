from django.urls import include, path

from apps.earnings import routers, views

urlpatterns = [
    path(
        "<uuid:member_uuid>/earnings/",
        views.EarningsView.as_view(),
        name="earnings",
    ),
    path(
        "<uuid:member_uuid>/missed/",
        views.MissedView.as_view(),
        name="missed",
    ),
    path("", include(routers.member_router.urls)),
]
