from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.serializers import ValidationError

from apps.members import models, serializers_create, serializers_get
from base import responses
from core import permissions
from core.pagination import StandardPagination


class ProfileView(GenericAPIView):
    permission_classes = [permissions.IsMember]
    serializer_class = serializers_get.MemberProfileSerializer

    def get(self, request, *args, **kwargs):
        member = request.user.member
        data = self.serializer_class(member, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditProfileSerializer)
    def patch(self, request, *args, **kwargs):
        serializer = serializers_create.EditProfileSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        member = request.user.member
        member.update(**serializer.validated_data)

        data = self.serializer_class(member, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class ChangePasswordView(GenericAPIView):
    permission_classes = [permissions.IsMember]
    serializer_class = serializers_create.ChangePasswordSerializer

    def patch(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        user = request.user
        if not user.check_password(validated_data["current_password"]):
            return responses.BadRequestError(
                details="Current password is incorrect"
            ).get_response()

        user.set_password(validated_data["password"])
        user.save()

        return responses.SuccessResponse(
            data={"message": "Password updated"}
        ).get_response()


class LoginAuditView(GenericAPIView):
    permission_classes = [permissions.IsMember]
    serializer_class = serializers_get.LoginAuditSerializer
    pagination_class = StandardPagination

    def get(self, request, *args, **kwargs):
        queryset = models.LoginAudit.objects.filter(
            member=request.user.member,
        ).order_by("-created")

        page = self.paginate_queryset(queryset)
        serializer = self.serializer_class(page, many=True, context={"request": self.request})
        return self.get_paginated_response(serializer.data)
