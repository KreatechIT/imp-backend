from rest_framework_nested import routers

from apps.earnings import viewsets

earnings_router = routers.DefaultRouter()
earnings_router.register("payouts", viewsets.PayoutViewSet, basename="payouts")


# SimpleRouter: DefaultRouter's api root view would shadow /members/
member_router = routers.SimpleRouter()
member_router.register(
    r'(?P<member_uuid>[0-9a-f-]{36})/payouts',
    viewsets.MemberPayoutViewSet,
    basename="member-payouts",
)
