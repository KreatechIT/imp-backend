from rest_framework import serializers

from apps.members import choices


class MemberSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    display_name = serializers.CharField(required=True)
    status = serializers.ChoiceField(
        choices=choices.MEMBER_STATUS_CHOICES, default=1,
    )
    affiliate_link = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    telegram_link = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    joined = serializers.DateField(required=False, allow_null=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        return attrs


class EditMemberSerializer(serializers.Serializer):
    display_name = serializers.CharField(required=False)
    status = serializers.ChoiceField(
        choices=choices.MEMBER_STATUS_CHOICES, required=False,
    )
    affiliate_link = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    telegram_link = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    joined = serializers.DateField(required=False, allow_null=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)


class EditProfileSerializer(serializers.Serializer):
    display_name = serializers.CharField(required=False)
    profile_picture = serializers.ImageField(required=False, allow_null=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        return attrs


class BankDetailSerializer(serializers.Serializer):
    bank = serializers.ChoiceField(choices=choices.BANK_CHOICES, required=True)
    account_holder_name = serializers.CharField(required=True)
    account_number = serializers.CharField(required=True)
    is_primary = serializers.BooleanField(default=True)


class PlatformAccountSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=choices.PLATFORM_CHOICES, required=True)
    handle = serializers.CharField(required=True)
    profile_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)
