from rest_framework_nested import routers

from apps.members import viewsets

member_router = routers.DefaultRouter()
member_router.register("", viewsets.MemberViewSet, basename="members")

profile_router = routers.DefaultRouter()
profile_router.register("bank-details", viewsets.BankDetailViewSet, basename="bank-details")
profile_router.register("platform-accounts", viewsets.PlatformAccountViewSet, basename="platform-accounts")
