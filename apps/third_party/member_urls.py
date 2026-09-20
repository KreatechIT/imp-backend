from django.urls import path

from . import views

urlpatterns = [
    path(
        "<uuid:member_uuid>/socialmedia/",
        views.SocialMediaConnectionView.as_view(),
        name="socialmedia-list",
    ),
    path(
        "<uuid:member_uuid>/socialmedia/start/",
        views.SocialMediaStartView.as_view(),
        name="socialmedia-start",
    ),
    path(
        "<uuid:member_uuid>/socialmedia/exchange/",
        views.SocialMediaExchangeView.as_view(),
        name="socialmedia-exchange",
    ),
    path(
        "<uuid:member_uuid>/socialmedia/<uuid:uuid>/disconnect/",
        views.SocialMediaDisconnectView.as_view(),
        name="socialmedia-disconnect",
    ),
]
