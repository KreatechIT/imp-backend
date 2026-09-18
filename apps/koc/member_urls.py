from django.urls import include, path

from apps.koc import routers, views

urlpatterns = [
    path("<uuid:member_uuid>/kpi/", views.MemberKpiView.as_view(), name="member-kpi"),
    path("", include(routers.member_router.urls)),
]
