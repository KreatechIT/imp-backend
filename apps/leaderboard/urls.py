from django.urls import path

from apps.leaderboard import views

urlpatterns = [
    path("kpi/", views.RankingKpiView.as_view(), name="kpi"),
    path("ranking/", views.RankingView.as_view(), name="ranking"),
    path("ranking/all/", views.AllRankingView.as_view(), name="ranking-all"),
    path(
        "ranking/member/<uuid:member_uuid>/",
        views.MemberRankingView.as_view(),
        name="ranking-member",
    ),
]
