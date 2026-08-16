from rest_framework_nested import routers

from apps.jobs import viewsets

job_router = routers.DefaultRouter()
job_router.register("companies", viewsets.CompanyViewSet, basename="companies")
job_router.register("postings", viewsets.JobViewSet, basename="postings")
job_router.register(r'postings/(?P<job_uuid>[^/.]+)/requirements', viewsets.JobRequirementViewSet, basename="requirements")
job_router.register("submissions", viewsets.SubmissionViewSet, basename="submissions")


# SimpleRouter: DefaultRouter's api root view would shadow /members/
member_router = routers.SimpleRouter()
member_router.register(r'(?P<member_uuid>[0-9a-f-]{36})/jobs', viewsets.MemberJobViewSet, basename="member-jobs")
member_router.register(r'(?P<member_uuid>[0-9a-f-]{36})/tasks', viewsets.MemberTaskViewSet, basename="member-tasks")
member_router.register(r'(?P<member_uuid>[0-9a-f-]{36})/available-jobs', viewsets.AvailableJobViewSet, basename="member-available-jobs")
