from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from apps.earnings import helper_functions, models, serializers_create, serializers_get
from apps.jobs.models import MemberJob
from apps.members.models import Member
from apps.notifications import helper_functions as notifications
from base import responses
from core import permissions
from core.pagination import StandardPagination


class JobPayoutViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.JobPayoutSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Job Payout Id"

    def get_queryset(self):
        queryset = models.JobPayout.objects.select_related(
            "member_job__member__user",
            "member_job__job__company",
            "reviewed_by__user",
        )
        params = self.request.query_params
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("job_uuid"):
            queryset = queryset.filter(member_job__job__uuid=params["job_uuid"])
        if params.get("member_uuid"):
            queryset = queryset.filter(member_job__member__uuid=params["member_uuid"])
        return queryset.order_by("-created")

    def get_job_payout(self, uuid):
        return (
            models.JobPayout.objects
            .select_for_update(of=("self",))
            .select_related("member_job__member__user", "member_job__job")
            .filter(uuid=uuid)
            .first()
        )

    def respond(self, payout):
        data = self.serializer_class(payout, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    def notify(self, payout, notification_type, title):
        member_job = payout.member_job
        notifications.notify(
            recipient=member_job.member.user,
            role=2,
            notification_type=notification_type,
            title=title,
            message=str(member_job.job.title),
        )

    @action(detail=True, methods=["patch"])
    def approve(self, request, uuid=None, *args, **kwargs):
        with transaction.atomic():
            payout = self.get_job_payout(uuid)
            if payout is None:
                return responses.MissingItemError(
                    item_key=self.item_key, item_id=uuid,
                ).get_response()
            if payout.status != 1:
                return responses.BadRequestError(
                    details="Only a pending payout request can be approved"
                ).get_response()

            payout.approve(request.user.admin)
            self.notify(payout, 12, "Payout approved")
        return self.respond(payout)

    @extend_schema(request=serializers_create.RejectJobPayoutSerializer)
    @action(detail=True, methods=["patch"])
    def reject(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.RejectJobPayoutSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        with transaction.atomic():
            payout = self.get_job_payout(uuid)
            if payout is None:
                return responses.MissingItemError(
                    item_key=self.item_key, item_id=uuid,
                ).get_response()
            if payout.status != 1:
                return responses.BadRequestError(
                    details="Only a pending payout request can be rejected"
                ).get_response()

            payout.reject(request.user.admin, serializer.validated_data["reject_reason"])
            self.notify(payout, 13, "Payout rejected")
        return self.respond(payout)

    @action(detail=True, methods=["patch"], url_path="mark-paid")
    def mark_paid(self, request, uuid=None, *args, **kwargs):
        with transaction.atomic():
            payout = self.get_job_payout(uuid)
            if payout is None:
                return responses.MissingItemError(
                    item_key=self.item_key, item_id=uuid,
                ).get_response()
            if payout.status != 2:
                return responses.BadRequestError(
                    details="Only an approved payout can be marked paid"
                ).get_response()

            payout.mark_paid()
            self.notify(payout, 14, "Payout paid")
        return self.respond(payout)


class MemberJobPayoutViewSet(GenericViewSet):
    serializer_class = serializers_get.JobPayoutSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"

    def get_member(self):
        member = Member.objects.filter(
            uuid=self.kwargs.get("member_uuid"), archived=None,
        ).select_related("user").first()
        if member is None:
            return None
        if member.user_id != self.request.user.id and not self.request.user.is_admin:
            return None
        return member

    def missing_member(self):
        return responses.MissingItemError(
            item_key="Member Id", item_id=self.kwargs.get("member_uuid"),
        ).get_response()

    def list(self, request, *args, **kwargs):
        member = self.get_member()
        if member is None:
            return self.missing_member()

        queryset = (
            models.JobPayout.objects
            .filter(member_job__member=member)
            .select_related(
                "member_job__member__user",
                "member_job__job__company",
                "reviewed_by__user",
            )
            .order_by("-created")
        )
        page = self.paginate_queryset(queryset)
        data = self.get_serializer(page, many=True).data
        return self.get_paginated_response(data)

    @extend_schema(responses=serializers_get.PayoutJobSerializer(many=True))
    @action(detail=False, methods=["get"])
    def jobs(self, request, *args, **kwargs):
        member = self.get_member()
        if member is None:
            return self.missing_member()

        rows = helper_functions.member_payout_jobs(member.uuid)
        data = serializers_get.PayoutJobSerializer(rows, many=True).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.JobPayoutRequestSerializer)
    def create(self, request, *args, **kwargs):
        member = self.get_member()
        if member is None:
            return self.missing_member()

        serializer = serializers_create.JobPayoutRequestSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        member_job_uuid = serializer.validated_data["member_job_uuid"]

        try:
            with transaction.atomic():
                member_job = (
                    MemberJob.objects
                    .select_for_update(of=("self",))
                    .select_related("job__company", "member__user")
                    .filter(uuid=member_job_uuid, member=member)
                    .first()
                )
                if member_job is None:
                    return responses.MissingItemError(
                        item_key="Member Job Id", item_id=member_job_uuid,
                    ).get_response()

                blocker = helper_functions.payout_blocker(member_job)
                if blocker:
                    return responses.BadRequestError(details=blocker).get_response()

                payout = models.JobPayout.objects.create(
                    member_job=member_job,
                    amount=helper_functions.job_payout_amount(member_job),
                )
        except IntegrityError:
            return responses.ExistingDataError(
                item_key="Job Payout", item_id=member_job_uuid,
            ).get_response()

        notifications.notify_admins(
            notification_type=11,
            title="Payout requested",
            message=f"{member.full_name or member.user.username} - {member_job.job.title}",
        )

        data = self.serializer_class(payout, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()
