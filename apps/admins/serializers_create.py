from rest_framework import serializers

from apps.admins import choices


class AdminSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    full_name = serializers.CharField(required=True)
    status = serializers.ChoiceField(
        choices=choices.ADMIN_STATUS_CHOICES, default=1,
    )
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        return attrs


class EditAdminSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False)
    status = serializers.ChoiceField(
        choices=choices.ADMIN_STATUS_CHOICES, required=False,
    )
    profile_picture = serializers.ImageField(required=False, allow_null=True)


class ResetAdminPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        return attrs
