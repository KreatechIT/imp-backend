from django.urls import include, path

from apps.front_view import routers, views

urlpatterns = [
    path("terms/public/<int:category>/", views.TermsPublicView.as_view(), name="terms-public"),
    path("influencer/leaderboard/", views.InfluencerLeaderboardView.as_view(), name="influencer-leaderboard"),
    path("influencer/rank/<str:phone_number>/", views.InfluencerRankView.as_view(), name="influencer-rank"),
    path("", include(routers.front_view_router.urls)),
]
