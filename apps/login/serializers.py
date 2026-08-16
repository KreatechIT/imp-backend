from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from base.models import UserModel


class TokenObtainSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, allow_blank=False)
    password = serializers.CharField(
        required=True,
        allow_blank=False,
        write_only=True,
        style={"input_type": "password"},
    )

    default_error_messages = {
        "no_active_account": _("Incorrect login credentials")
    }

    def validate(self, attrs):
        self.user = UserModel.objects.filter(username=attrs["username"]).first()

        if self.user is None:
            return None

        if not self.user.check_password(attrs["password"]):
            return None

        if self.user.is_archived:
            return None

        if self.user.is_admin:
            return {"type": "admin"}
        if self.user.is_member:
            return {"type": "member"}

        return None

    @classmethod
    def get_token(cls, user):
        return RefreshToken.for_user(user)

    def add_tokens(self, data):
        refresh = self.get_token(self.user)
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        return data


class AdminTokenObtainPairSerializer(TokenObtainSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        if data is None or data.get("type") != "admin":
            return {"message": "error"}

        return self.add_tokens(data)


class MemberTokenObtainPairSerializer(TokenObtainSerializer):
    ip_address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    device = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        data = super().validate(attrs)

        if data is None or data.get("type") != "member":
            return {"message": "error"}

        data["ip_address"] = attrs.get("ip_address") or None
        data["device"] = attrs.get("device") or None

        return self.add_tokens(data)


class CustomRefreshTokenSerializer(TokenRefreshSerializer):
    pass
