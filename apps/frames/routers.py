from rest_framework_nested import routers

from apps.frames import viewsets

# SimpleRouter: the api root view would shadow the jobs router mounted
# at the same prefix.
frame_router = routers.SimpleRouter()
frame_router.register(
    r'org/(?P<org_uuid>[^/.]+)/job/(?P<job_uuid>[^/.]+)/frames',
    viewsets.FrameViewSet,
    basename="frames",
)

member_router = routers.SimpleRouter()
member_router.register(
    r'(?P<member_uuid>[0-9a-f-]{36})/jobs/(?P<job_uuid>[^/.]+)/frames',
    viewsets.MemberFrameViewSet,
    basename="member-frames",
)

# Flat frame-library routes, addressed by frame uuid rather than nested
# under an org/job path. SimpleRouter: DefaultRouter's api root view
# can't cope with the regex-prefixed job/<uuid> registration below.
library_router = routers.SimpleRouter()
library_router.register(
    "library", viewsets.FrameLibraryViewSet, basename="frame-library",
)
library_router.register(
    "content", viewsets.OriginalContentViewSet, basename="frame-content",
)
library_router.register(
    r'job/(?P<job_uuid>[^/.]+)', viewsets.FrameByJobViewSet, basename="frame-by-job",
)
