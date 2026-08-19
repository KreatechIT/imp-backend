from rest_framework import serializers

from apps.members import models


class BankDetailSerializer(serializers.ModelSerializer):
    bank = serializers.CharField(source="get_bank_display")
    bank_code = serializers.IntegerField(source="bank")

    class Meta:
        model = models.BankDetail
        fields = [
            "uuid",
            "bank",
            "bank_code",
            "account_holder_name",
            "account_number",
            "is_primary",
        ]


class PlatformAccountSerializer(serializers.ModelSerializer):
    platform = serializers.CharField(source="get_platform_display")

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


class MemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")
    status = serializers.CharField(source="get_status_display")
    last_login = serializers.DateTimeField(source="user.last_login")

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
