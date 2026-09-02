from django.urls import include, path

from apps.front_view import routers, views

urlpatterns = [
    path("terms/public/<int:category>/", views.TermsPublicView.as_view(), name="terms-public"),
    path("", include(routers.front_view_router.urls)),
]
