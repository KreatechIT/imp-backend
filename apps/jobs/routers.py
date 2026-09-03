from rest_framework_nested import routers

from apps.jobs import viewsets

# Admin routes all hang off an org: /jobs/org/{org_uuid}/job/{job_uuid}/...
# so the parent uuids come from the path instead of the request body.
job_router = routers.DefaultRouter()
job_router.register("org", viewsets.OrgViewSet, basename="org")
job_router.register(
    r'org/(?P<org_uuid>[^/.]+)/job',
    viewsets.JobViewSet,
    basename="job",
)
# Flat, cross-org job list alongside the org-scoped route above: /jobs/list/
job_router.register("list", viewsets.JobListViewSet, basename="job-list")
job_router.register(
    r'org/(?P<org_uuid>[^/.]+)/job/(?P<job_uuid>[^/.]+)/requirement',
    viewsets.JobRequirementViewSet,
    basename="requirement",
)
job_router.register(
    r'org/(?P<org_uuid>[^/.]+)/job/(?P<job_uuid>[^/.]+)/member',
    viewsets.JobMemberViewSet,
    basename="job-member",
)
job_router.register(
    r'job/(?P<job_uuid>[^/.]+)/submission',
    viewsets.SubmissionViewSet,
    basename="submission",
)


# SimpleRouter: DefaultRouter's api root view would shadow /members/
member_router = routers.SimpleRouter()
member_router.register(r'(?P<member_uuid>[0-9a-f-]{36})/jobs', viewsets.MemberJobViewSet, basename="member-jobs")
member_router.register(r'(?P<member_uuid>[0-9a-f-]{36})/tasks', viewsets.MemberTaskViewSet, basename="member-tasks")
member_router.register(r'(?P<member_uuid>[0-9a-f-]{36})/available-jobs', viewsets.AvailableJobViewSet, basename="member-available-jobs")
