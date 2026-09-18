from rest_framework_nested import routers

from apps.koc import viewsets

member_router = routers.SimpleRouter()
member_router.register(
    r'(?P<member_uuid>[0-9a-f-]{36})/submissions',
    viewsets.MemberSubmissionViewSet,
    basename="member-submissions",
)

admin_router = routers.SimpleRouter()
admin_router.register(
    "submissions", viewsets.AdminSubmissionViewSet, basename="admin-submissions",
)
