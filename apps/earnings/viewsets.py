from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.earnings import models, serializers_create, serializers_get
from apps.members.models import Member
from base import responses
from core import permissions
from core.pagination import StandardPagination


class PayoutViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.PayoutSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Payout Id"

    def get_queryset(self):
        queryset = (
            models.Payout.objects
            .filter(archived=None)
            .select_related("member__user")
        )
        member_uuid = self.request.query_params.get("member_uuid")
        period_key = self.request.query_params.get("period_key")
        status = self.request.query_params.get("status")

        if member_uuid:
            queryset = queryset.filter(member__uuid=member_uuid)
        if period_key:
            queryset = queryset.filter(period_key=period_key)
        if status == "2":
            queryset = queryset.exclude(paid_at=None)
        elif status == "1":
            queryset = queryset.filter(paid_at=None)
        return queryset.order_by("-period_key", "-created")

    @extend_schema(request=serializers_create.PayoutSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.PayoutSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        member_uuid = validated_data.pop("member_uuid")
        member = Member.objects.filter(uuid=member_uuid, archived=None).first()
        if member is None:
            return responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        try:
            with transaction.atomic():
                payout = models.Payout.objects.create(
                    member=member, **validated_data
                )
        except IntegrityError:
            return responses.ExistingDataError(
                item_key="Payout", item_id=validated_data["period_key"],
            ).get_response()

        data = self.serializer_class(payout).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditPayoutSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditPayoutSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        payout = self.get_payout(uuid)
        if payout is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if payout.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        payout.update(**serializer.validated_data)

        data = self.serializer_class(payout).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditPayoutSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    def get_payout(self, uuid):
        return models.Payout.objects.filter(uuid=uuid).first()

    @action(detail=True, methods=["patch"], url_path="mark-paid")
    def mark_paid(self, request, uuid=None, *args, **kwargs):
        payout = self.get_payout(uuid)
        if payout is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if payout.paid_at:
            return responses.BadRequestError(
                details="Payout has already been marked paid"
            ).get_response()

        payout.mark_paid()

        data = self.serializer_class(payout).data
        return responses.SuccessResponse(data=data).get_response()

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        payout = self.get_payout(uuid)
        if payout is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if payout.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        payout.archive()

        data = self.serializer_class(payout).data
        return responses.SuccessResponse(data=data).get_response()


class MemberPayoutViewSet(ReadOnlyModelViewSet):
    """The member's own payment history."""

    serializer_class = serializers_get.PayoutSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"

    def get_queryset(self):
        return (
            models.Payout.objects
            .filter(
                member__uuid=self.kwargs.get("member_uuid"),
                archived=None,
            )
            .select_related("member__user")
            .order_by("-period_key")
        )
