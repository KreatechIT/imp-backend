from rest_framework import routers

from . import viewsets

member_router = routers.SimpleRouter()
member_router.register(
    r"(?P<member_uuid>[0-9a-f-]{36})/socialmedia",
    viewsets.SocialMediaConnectionViewSet,
    basename="socialmedia",
)
