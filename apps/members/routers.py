from rest_framework_nested import routers

from apps.members import viewsets

member_router = routers.DefaultRouter()
member_router.register("", viewsets.MemberViewSet, basename="members")

# SimpleRouter: DefaultRouter's api root view would shadow /members/
admin_member_router = routers.SimpleRouter()
admin_member_router.register(
    r'(?P<member_uuid>[0-9a-f-]{36})/bank-details',
    viewsets.MemberBankDetailViewSet,
    basename="member-bank-details",
)
admin_member_router.register(
    r'(?P<member_uuid>[0-9a-f-]{36})/audit_login',
    viewsets.MemberLoginAuditViewSet,
    basename="member-audit-login",
)

profile_router = routers.DefaultRouter()
profile_router.register("bank-details", viewsets.BankDetailViewSet, basename="bank-details")
profile_router.register("platform-accounts", viewsets.PlatformAccountViewSet, basename="platform-accounts")
