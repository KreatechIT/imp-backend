from rest_framework_nested import routers

from apps.earnings import job_payout_viewsets, viewsets

earnings_router = routers.DefaultRouter()
earnings_router.register("payouts", viewsets.PayoutViewSet, basename="payouts")
earnings_router.register(
    "job-payouts", job_payout_viewsets.JobPayoutViewSet, basename="job-payouts",
)


# SimpleRouter: DefaultRouter's api root view would shadow /members/
member_router = routers.SimpleRouter()
member_router.register(
    r'(?P<member_uuid>[0-9a-f-]{36})/payouts',
    viewsets.MemberPayoutViewSet,
    basename="member-payouts",
)
member_router.register(
    r'(?P<member_uuid>[0-9a-f-]{36})/job-payouts',
    job_payout_viewsets.MemberJobPayoutViewSet,
    basename="member-job-payouts",
)
