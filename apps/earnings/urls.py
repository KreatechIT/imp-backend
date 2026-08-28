from django.urls import include, path

from apps.earnings import routers, views

urlpatterns = [
    path(
        "statistics/",
        views.EarningsStatisticsView.as_view(),
        name="statistics",
    ),
    path("kpi/", views.EarningsKpiView.as_view(), name="kpi"),
    path("", include(routers.earnings_router.urls)),
]
