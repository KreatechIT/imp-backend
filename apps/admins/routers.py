from rest_framework_nested import routers

from apps.admins import viewsets

admin_router = routers.DefaultRouter()
admin_router.register("users", viewsets.AdminViewSet, basename="users")
admin_router.register("activity-log", viewsets.ActivityLogViewSet, basename="activity-log")
