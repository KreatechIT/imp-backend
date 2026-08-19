from rest_framework_nested import routers

from apps.front_view import viewsets

front_view_router = routers.DefaultRouter()
front_view_router.register("banners", viewsets.BannerViewSet, basename="banners")
front_view_router.register("guides", viewsets.GuideViewSet, basename="guides")
front_view_router.register("terms", viewsets.TermsAndConditionsViewSet, basename="terms")
front_view_router.register("content", viewsets.ContentViewSet, basename="content")
