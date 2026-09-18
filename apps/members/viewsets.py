from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.members import models, serializers_create, serializers_get
from base import responses
from base.models import UserModel
from base.utils import log_action
from core import permissions
from core.pagination import StandardPagination


class MemberViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.MemberSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Member Id"

    def get_queryset(self):
        queryset = (
            models.Member.objects
            .filter(archived=None)
            .select_related("user")
            .order_by("-created")
        )

        search = self.request.query_params.get("search")
        username = self.request.query_params.get("username")
        status = self.request.query_params.get("status")
        from_date = self.request.query_params.get("from_date")
        to_date = self.request.query_params.get("to_date")

        if from_date and to_date:
            queryset = queryset.filter(created__date__range=(from_date, to_date))
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(user__username__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(email__icontains=search)
                | Q(bank_details__account_number__icontains=search)
                | Q(bank_details__account_holder_name__icontains=search)
            ).distinct()
        if username:
            queryset = queryset.filter(user__username__icontains=username)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers_get.MemberProfileSerializer
        return serializers_get.MemberSerializer

    @extend_schema(request=serializers_create.MemberSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.MemberSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        username = validated_data.pop("username")
        password = validated_data.pop("password")
        validated_data.pop("confirm_password")

        role_uuid = validated_data.pop("role_uuid", None)
        role = None
        if role_uuid:
            try:
                role = models.Role.objects.get(uuid=role_uuid)
            except models.Role.DoesNotExist:
                return responses.MissingItemError(
                    item_key="Role", item_id=role_uuid,
                ).get_response()

        if UserModel.objects.filter(username=username).exists():
            return responses.ExistingDataError(
                item_key="Username", item_id=username,
            ).get_response()

        try:
            with transaction.atomic():
                user = UserModel.objects.create(username=username)
                user.set_password(password)
                user.save()
                member = models.Member.objects.create(
                    user=user, role=role, **validated_data
                )
        except IntegrityError:
            return responses.ExistingDataError(
                error_message="Phone number or email already exists",
            ).get_response()

        data = serializers_get.MemberSerializer(member, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditMemberSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditMemberSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        if "role_uuid" in validated_data:
            role_uuid = validated_data.pop("role_uuid")
            role = None
            if role_uuid:
                try:
                    role = models.Role.objects.get(uuid=role_uuid)
                except models.Role.DoesNotExist:
                    return responses.MissingItemError(
                        item_key="Role", item_id=role_uuid,
                    ).get_response()
            validated_data["role"] = role

        try:
            member = models.Member.objects.get(uuid=uuid)
        except models.Member.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if member.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        try:
            with transaction.atomic():
                member.update(**validated_data)
        except IntegrityError:
            return responses.ExistingDataError(
                error_message="Phone number or email already exists",
            ).get_response()

        data = serializers_get.MemberSerializer(member, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditMemberSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @extend_schema(request=serializers_create.ResetPasswordSerializer)
    @action(detail=True, methods=["patch"], url_path="change-password")
    def change_password(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.ResetPasswordSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        try:
            member = models.Member.objects.get(uuid=uuid)
        except models.Member.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        user = member.user
        user.set_password(validated_data["password"])
        user.save()

        log_action(
            actor=request.user,
            action="member.password_reset",
            target=member,
            detail=f"Password reset for {member}",
        )

        data = serializers_get.MemberSerializer(member, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            member = models.Member.objects.get(uuid=uuid)
        except models.Member.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if member.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        member.archive()
        member.user.archive()

        data = serializers_get.MemberSerializer(member, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class RoleViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.RoleSerializer
    permission_classes = [permissions.IsAdmin]
    lookup_field = "uuid"

    def get_queryset(self):
        return models.Role.objects.filter(archived=None).order_by("name")


class UserGroupViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.UserGroupSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "User Group Id"

    def base_queryset(self):
        active_members = models.Member.objects.filter(
            archived=None,
        ).select_related("user", "role").order_by("full_name")

        return (
            models.UserGroup.objects
            .annotate(
                total_members=Count(
                    "members",
                    filter=Q(members__archived__isnull=True),
                    distinct=True,
                ),
            )
            .prefetch_related(Prefetch("members", queryset=active_members))
        )

    def get_queryset(self):
        queryset = self.base_queryset().filter(archived=None).order_by("name")

        name = self.request.query_params.get("name")
        status = self.request.query_params.get("status")
        if name:
            queryset = queryset.filter(name__icontains=name)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def serialized(self, user_group):
        instance = self.base_queryset().get(pk=user_group.pk)
        return serializers_get.UserGroupSerializer(
            instance, context={"request": self.request},
        ).data

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers_get.UserGroupDetailSerializer
        return serializers_get.UserGroupSerializer

    def get_members(self, member_uuids):
        members = list(
            models.Member.objects.filter(uuid__in=member_uuids, archived=None)
        )
        found = {str(member.uuid) for member in members}
        missing = [str(uuid) for uuid in member_uuids if str(uuid) not in found]
        return members, missing

    @extend_schema(request=serializers_create.UserGroupSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.UserGroupSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        member_uuids = validated_data.pop("members", [])
        members, missing = self.get_members(member_uuids)
        if missing:
            return responses.MissingItemError(
                item_key="Member Id", item_id=", ".join(missing),
            ).get_response()

        try:
            with transaction.atomic():
                user_group = models.UserGroup.objects.create(**validated_data)
                user_group.members.set(members)
        except IntegrityError:
            return responses.ExistingDataError(
                item_key="Name", item_id=validated_data["name"],
            ).get_response()

        return responses.CreatedSuccessResponse(
            data=self.serialized(user_group),
        ).get_response()

    @extend_schema(request=serializers_create.EditUserGroupSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditUserGroupSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        try:
            user_group = models.UserGroup.objects.get(uuid=uuid)
        except models.UserGroup.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if user_group.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        members = None
        if "members" in validated_data:
            member_uuids = validated_data.pop("members")
            members, missing = self.get_members(member_uuids)
            if missing:
                return responses.MissingItemError(
                    item_key="Member Id", item_id=", ".join(missing),
                ).get_response()

        try:
            with transaction.atomic():
                user_group.update(**validated_data)
                if members is not None:
                    user_group.members.set(members)
        except IntegrityError:
            return responses.ExistingDataError(
                item_key="Name", item_id=validated_data.get("name"),
            ).get_response()

        return responses.SuccessResponse(
            data=self.serialized(user_group),
        ).get_response()

    @extend_schema(request=serializers_create.EditUserGroupSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            user_group = models.UserGroup.objects.get(uuid=uuid)
        except models.UserGroup.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if user_group.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        user_group.archive()

        return responses.SuccessResponse(
            data=self.serialized(user_group),
        ).get_response()


class BankDetailViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.BankDetailSerializer
    permission_classes = [permissions.IsMember]
    lookup_field = "uuid"
    item_key = "Bank Detail Id"

    def get_member(self):
        return self.request.user.member

    def get_queryset(self):
        return (
            models.BankDetail.objects
            .filter(member=self.get_member(), archived=None)
            .order_by("-is_primary", "-created")
        )

    @extend_schema(request=serializers_create.BankDetailSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.BankDetailSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        member = self.get_member()

        if validated_data.get("is_primary"):
            models.BankDetail.objects.filter(
                member=member, archived=None,
            ).update(is_primary=False)

        bank_detail = models.BankDetail.objects.create(
            member=member, **validated_data
        )

        data = self.serializer_class(bank_detail, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditBankDetailSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditBankDetailSerializer(
            data=request.data
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        member = self.get_member()

        try:
            bank_detail = models.BankDetail.objects.get(uuid=uuid, member=member)
        except models.BankDetail.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if bank_detail.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if validated_data.get("is_primary"):
            models.BankDetail.objects.filter(
                member=member, archived=None,
            ).exclude(pk=bank_detail.pk).update(is_primary=False)

        bank_detail.update(**validated_data)

        data = self.serializer_class(bank_detail, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditBankDetailSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            bank_detail = models.BankDetail.objects.get(
                uuid=uuid, member=self.get_member(),
            )
        except models.BankDetail.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if bank_detail.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        bank_detail.archive()

        data = self.serializer_class(bank_detail, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class MemberBankDetailViewSet(ReadOnlyModelViewSet):
    """Admin view of one member's bank accounts, for paying them."""

    serializer_class = serializers_get.AdminBankDetailSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Bank Detail Id"

    def get_queryset(self):
        return models.BankDetail.objects.filter(
            member__uuid=self.kwargs.get("member_uuid"), archived=None,
        ).select_related("member__user").order_by("-is_primary", "-created")


class MemberLoginAuditViewSet(ReadOnlyModelViewSet):
    """Admin view of one member's login history, latest first."""

    serializer_class = serializers_get.LoginAuditSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Login Audit Id"

    def get_queryset(self):
        return models.LoginAudit.objects.filter(
            member__uuid=self.kwargs.get("member_uuid"),
        ).order_by("-created")


class PlatformAccountViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.PlatformAccountSerializer
    permission_classes = [permissions.IsMember]
    lookup_field = "uuid"
    item_key = "Platform Account Id"

    def get_member(self):
        return self.request.user.member

    def get_queryset(self):
        return (
            models.PlatformAccount.objects
            .filter(member=self.get_member(), archived=None)
            .order_by("platform")
        )

    @extend_schema(request=serializers_create.PlatformAccountSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.PlatformAccountSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        try:
            with transaction.atomic():
                platform_account = models.PlatformAccount.objects.create(
                    member=self.get_member(), **validated_data
                )
        except IntegrityError:
            return responses.ExistingDataError(
                item_key="Platform", item_id=validated_data["platform"],
            ).get_response()

        data = self.serializer_class(platform_account, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditPlatformAccountSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditPlatformAccountSerializer(
            data=request.data
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        try:
            platform_account = models.PlatformAccount.objects.get(
                uuid=uuid, member=self.get_member(),
            )
        except models.PlatformAccount.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        platform_account.update(**validated_data)

        data = self.serializer_class(platform_account, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditPlatformAccountSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            platform_account = models.PlatformAccount.objects.get(
                uuid=uuid, member=self.get_member(),
            )
        except models.PlatformAccount.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        platform_account.archive()

        data = self.serializer_class(platform_account, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()
