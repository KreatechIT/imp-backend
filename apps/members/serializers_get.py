from rest_framework import serializers

from apps.members import models


class BankDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.BankDetail
        fields = [
            "uuid",
            "bank",
            "account_holder_name",
            "account_number",
            "is_primary",
        ]


class AdminBankDetailSerializer(BankDetailSerializer):
    """What an admin sees when checking who to pay."""

    member = serializers.CharField(source="member.full_name")
    member_uuid = serializers.UUIDField(source="member.uuid")
    username = serializers.CharField(source="member.user.username")

    class Meta(BankDetailSerializer.Meta):
        fields = BankDetailSerializer.Meta.fields + [
            "member",
            "member_uuid",
            "username",
            "created",
            "modified",
        ]


class LoginAuditSerializer(serializers.ModelSerializer):
    datetime = serializers.DateTimeField(source="created")

    class Meta:
        model = models.LoginAudit
        fields = [
            "uuid",
            "datetime",
            "ip_address",
            "device",
        ]


class PlatformAccountSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.PlatformAccount
        fields = [
            "uuid",
            "platform",
            "handle",
            "profile_url",
            "is_verified",
            "last_synced",
        ]


class RoleSerializer(serializers.ModelSerializer):
    total_assigned = serializers.SerializerMethodField()
    status = serializers.CharField(source="get_status_display")

    def get_total_assigned(self, obj):
        return obj.members.all().count()

    class Meta:
        model = models.Role
        fields = [
            "uuid",
            "name",
            "status",
            "total_assigned",
        ]


class UserGroupMemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")
    member_role = serializers.SerializerMethodField()

    def get_member_role(self, obj):
        return obj.role.name if obj.role else None

    class Meta:
        model = models.Member
        fields = [
            "uuid",
            "username",
            "full_name",
            "phone_number",
            "date_of_birth",
            "member_role",
        ]


class UserGroupSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source="get_status_display")
    total_members = serializers.IntegerField(read_only=True)

    class Meta:
        model = models.UserGroup
        fields = [
            "uuid",
            "name",
            "status",
            "total_members",
            "created",
        ]


class UserGroupDetailSerializer(UserGroupSerializer):
    members = UserGroupMemberSerializer(many=True, read_only=True)

    class Meta(UserGroupSerializer.Meta):
        fields = UserGroupSerializer.Meta.fields + ["members"]


class MemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")
    last_login = serializers.DateTimeField(source="user.last_login")
    member_role = serializers.SerializerMethodField()

    def get_member_role(self, obj):
        return obj.role.name if obj.role else None

    class Meta:
        model = models.Member
        fields = [
            "uuid",
            "username",
            "full_name",
            "phone_number",
            "email",
            "date_of_birth",
            "profile_picture",
            "status",
            "member_role",
            "joined",
            "last_login",
            "created",
        ]


class MemberProfileSerializer(MemberSerializer):
    bank_details = serializers.SerializerMethodField()
    platform_accounts = serializers.SerializerMethodField()

    def get_bank_details(self, obj):
        queryset = obj.bank_details.filter(archived=None).order_by("-is_primary")
        return BankDetailSerializer(queryset, many=True).data

    def get_platform_accounts(self, obj):
        queryset = obj.platform_accounts.filter(archived=None).order_by("platform")
        return PlatformAccountSerializer(queryset, many=True).data

    class Meta(MemberSerializer.Meta):
        fields = MemberSerializer.Meta.fields + [
            "bank_details",
            "platform_accounts",
        ]
