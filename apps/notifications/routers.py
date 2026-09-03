from rest_framework_nested import routers

from apps.notifications import viewsets

notification_router = routers.SimpleRouter()
notification_router.register(
    "", viewsets.NotificationViewSet, basename="notifications",
)
