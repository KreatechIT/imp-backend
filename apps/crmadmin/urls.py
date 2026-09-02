from django.urls import include, path

from apps.crmadmin import routers, views

urlpatterns = [
    path("dashboard/kpi/", views.DashboardKpiView.as_view(), name="dashboard-kpi"),
    path("", include(routers.admin_router.urls)),
]
