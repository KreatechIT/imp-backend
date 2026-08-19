from rest_framework import serializers

from apps.members import choices


class MemberSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    full_name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
    )
    phone_number = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=20,
    )
    email = serializers.EmailField(
        required=False, allow_null=True, allow_blank=True,
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=choices.MEMBER_STATUS_CHOICES, default=1,
    )
    joined = serializers.DateField(required=False, allow_null=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate_phone_number(self, value):
        return value or None

    def validate_email(self, value):
        return value or None

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        return attrs


class EditMemberSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False)
    phone_number = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=20,
    )
    email = serializers.EmailField(
        required=False, allow_null=True, allow_blank=True,
    )
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=choices.MEMBER_STATUS_CHOICES, required=False,
    )
    joined = serializers.DateField(required=False, allow_null=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    def validate_phone_number(self, value):
        return value or None

    def validate_email(self, value):
        return value or None


class EditProfileSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False)
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


class BankDetailSerializer(serializers.Serializer):
    bank = serializers.ChoiceField(choices=choices.BANK_CHOICES, required=True)
    account_holder_name = serializers.CharField(required=True)
    account_number = serializers.CharField(required=True)
    is_primary = serializers.BooleanField(default=True)


class PlatformAccountSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=choices.PLATFORM_CHOICES, required=True)
    handle = serializers.CharField(required=True)
    profile_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)
