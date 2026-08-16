from django.contrib.auth.models import update_last_login
from rest_framework.serializers import ValidationError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.admins.models import Admin
from apps.admins.serializers_get import AdminSerializer
from apps.login import serializers
from apps.members.models import LoginAudit, Member
from apps.members.serializers_get import MemberProfileSerializer
from base import responses


class AdminAccessTokenView(TokenObtainPairView):
    serializer_class = serializers.AdminTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        except TokenError as e:
            raise InvalidToken(e.args[0])

        validated_data = serializer.validated_data

        if validated_data.get("message") == "error":
            return responses.PermissionDeniedError(
                error_message="Incorrect login credentials"
            ).get_response()

        admin = Admin.objects.get(user=serializer.user)
        update_last_login(None, serializer.user)

        data = AdminSerializer(admin).data
        data["access"] = validated_data["access"]
        data["refresh"] = validated_data["refresh"]
        data["role"] = "ADMIN"

        return responses.SuccessResponse(data=data).get_response()


class MemberAccessTokenView(TokenObtainPairView):
    serializer_class = serializers.MemberTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        except TokenError as e:
            raise InvalidToken(e.args[0])

        validated_data = serializer.validated_data

        if validated_data.get("message") == "error":
            return responses.PermissionDeniedError(
                error_message="Incorrect login credentials"
            ).get_response()

        member = Member.objects.get(user=serializer.user)
        update_last_login(None, serializer.user)

        LoginAudit.objects.create(
            member=member,
            ip_address=validated_data.get("ip_address"),
            device=validated_data.get("device"),
        )

        data = MemberProfileSerializer(member).data
        data["access"] = validated_data["access"]
        data["refresh"] = validated_data["refresh"]
        data["role"] = "MEMBER"

        return responses.SuccessResponse(data=data).get_response()


class CustomRefreshTokenView(TokenRefreshView):
    serializer_class = serializers.CustomRefreshTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        validated_data = serializer.validated_data

        data = {
            "access": validated_data["access"],
            "refresh": validated_data.get("refresh"),
        }
        return responses.SuccessResponse(data=data).get_response()
