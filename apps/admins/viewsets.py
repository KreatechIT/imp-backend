from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.admins import models, serializers_create, serializers_get
from base import responses
from base.models import UserModel
from core import permissions
from core.pagination import StandardPagination


class AdminViewSet(ReadOnlyModelViewSet):
    queryset = models.Admin.objects.filter(archived=None).order_by("-created")
    serializer_class = serializers_get.AdminSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Admin Id"

    def get_queryset(self):
        queryset = self.queryset
        username = self.request.query_params.get("username")
        status = self.request.query_params.get("status")
        if username:
            queryset = queryset.filter(user__username__icontains=username)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    @extend_schema(request=serializers_create.AdminSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.AdminSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        username = validated_data.pop("username")
        password = validated_data.pop("password")
        validated_data.pop("confirm_password")

        try:
            user = UserModel.objects.create(username=username)
        except IntegrityError:
            return responses.ExistingDataError(
                item_key="Username", item_id=username,
            ).get_response()

        user.set_password(password)
        user.save()

        admin = models.Admin.objects.create(user=user, **validated_data)

        data = self.serializer_class(admin).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditAdminSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditAdminSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        try:
            admin = models.Admin.objects.get(uuid=uuid)
        except models.Admin.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if admin.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        admin.update(**validated_data)

        data = self.serializer_class(admin).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditAdminSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @extend_schema(request=serializers_create.ResetAdminPasswordSerializer)
    @action(detail=True, methods=["patch"])
    def resetpassword(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.ResetAdminPasswordSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        try:
            admin = models.Admin.objects.get(uuid=uuid)
        except models.Admin.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        user = admin.user
        user.set_password(validated_data["password"])
        user.save()

        data = self.serializer_class(admin).data
        return responses.SuccessResponse(data=data).get_response()

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            admin = models.Admin.objects.get(uuid=uuid)
        except models.Admin.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if admin.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        admin.archive()
        admin.user.archive()

        data = self.serializer_class(admin).data
        return responses.SuccessResponse(data=data).get_response()


class ActivityLogViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.ActivityLogSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"

    def get_queryset(self):
        queryset = models.ActivityLog.objects.all().order_by("-created")
        username = self.request.query_params.get("username")
        if username:
            queryset = queryset.filter(admin__user__username__icontains=username)
        return queryset
