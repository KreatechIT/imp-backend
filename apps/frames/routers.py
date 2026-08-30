from rest_framework_nested import routers

from apps.frames import viewsets

# SimpleRouter: the api root view would shadow the jobs router mounted
# at the same prefix.
frame_router = routers.SimpleRouter()
frame_router.register(
    r'postings/(?P<job_uuid>[^/.]+)/frames',
    viewsets.FrameViewSet,
    basename="frames",
)

member_router = routers.SimpleRouter()
member_router.register(
    r'(?P<member_uuid>[0-9a-f-]{36})/jobs/(?P<job_uuid>[^/.]+)/frames',
    viewsets.MemberFrameViewSet,
    basename="member-frames",
)
