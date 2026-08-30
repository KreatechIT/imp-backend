from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.jobs import (
    helper_functions,
    models,
    serializers_create,
    serializers_get,
)
from apps.members.models import Member
from base import responses
from core import permissions
from core.pagination import StandardPagination


class MemberJobViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.MemberJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Member Job Id"

    def get_queryset(self):
        queryset = (
            models.MemberJob.objects
            .filter(member__uuid=self.kwargs.get("member_uuid"), archived=None)
            .select_related("member__user", "job__company")
            .order_by("-created")
        )
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_member_job(self, uuid):
        return models.MemberJob.objects.filter(
            uuid=uuid,
            member__uuid=self.kwargs.get("member_uuid"),
            archived=None,
        ).first()

    def apply_update(self, uuid, **updates):
        if not self.request.user.is_admin:
            return responses.BadRequestError(
                "Can only be triggered by admins"
            ).get_response()

        member_job = self.get_member_job(uuid)
        if member_job is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        member_job.update(**updates)

        data = self.serializer_class(member_job, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditMemberJobSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditMemberJobSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        return self.apply_update(uuid, **serializer.validated_data)

    @extend_schema(request=serializers_create.ApproveMemberJobSerializer)
    @action(detail=True, methods=["patch"])
    def approve(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.ApproveMemberJobSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        updates = {"status": 2, "joined": timezone.localdate()}
        affiliate_link = serializer.validated_data.get("affiliate_link")
        if affiliate_link:
            updates["affiliate_link"] = affiliate_link
            updates["affiliate_link_status"] = 3

        return self.apply_update(uuid, **updates)

    @action(detail=True, methods=["patch"])
    def reject(self, request, uuid=None, *args, **kwargs):
        return self.apply_update(uuid, status=4)

    @action(detail=True, methods=["patch"])
    def complete(self, request, uuid=None, *args, **kwargs):
        return self.apply_update(uuid, status=3, completed=timezone.localdate())


class AvailableJobViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.AvailableJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Job Id"

    def get_queryset(self):
        return (
            models.Job.objects
            .filter(archived=None, status=2)
            .select_related("company")
            .prefetch_related("requirements")
            .order_by("-created")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["applied_job_ids"] = set(
            models.MemberJob.objects
            .filter(member__uuid=self.kwargs.get("member_uuid"), archived=None)
            .values_list("job_id", flat=True)
        )
        return context

    @action(detail=True, methods=["post"])
    def apply(self, request, uuid=None, *args, **kwargs):
        member_uuid = self.kwargs.get("member_uuid")
        member = Member.objects.filter(uuid=member_uuid, archived=None).first()
        if member is None:
            return responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        try:
            job = models.Job.objects.get(uuid=uuid, archived=None)
        except models.Job.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if not job.is_live:
            return responses.BadRequestError(
                details="Job is not open for applications"
            ).get_response()

        try:
            with transaction.atomic():
                member_job = models.MemberJob.objects.create(
                    member=member, job=job, status=1,
                )
        except IntegrityError:
            return responses.ExistingDataError(
                error_message="Already applied to this job",
            ).get_response()

        data = serializers_get.MemberJobSerializer(
            member_job, context={"request": self.request},
        ).data
        return responses.CreatedSuccessResponse(data=data).get_response()


class MemberTaskViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.MemberTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Task Id"

    def get_queryset(self):
        queryset = (
            models.MemberTask.objects
            .filter(member_job__member__uuid=self.kwargs.get("member_uuid"))
            .select_related(
                "member_job__member__user",
                "member_job__job__company",
                "requirement",
            )
            .order_by("-period_start", "requirement__content_type")
        )

        member_job_uuid = self.request.query_params.get("member_job_uuid")
        period_key = self.request.query_params.get("period_key")
        if member_job_uuid:
            queryset = queryset.filter(member_job__uuid=member_job_uuid)
        if period_key:
            queryset = queryset.filter(period_key=period_key)
        return queryset

    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request, *args, **kwargs):
        queryset = helper_functions.ensure_today_tasks(
            self.kwargs.get("member_uuid")
        )

        data = self.serializer_class(queryset, many=True, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.SubmitTaskSerializer)
    @action(detail=True, methods=["post", "patch"])
    def submit(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.SubmitTaskSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        try:
            task = models.MemberTask.objects.get(
                uuid=uuid,
                member_job__member__uuid=self.kwargs.get("member_uuid"),
            )
        except models.MemberTask.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if task.is_submitted:
            return responses.BadRequestError(
                details="Task has already been submitted"
            ).get_response()

        settings_row = models.JobSettings.objects.first()
        grace_hours = settings_row.submission_grace_hours if settings_row else 0
        deadline = timezone.make_aware(
            datetime.combine(task.period_end, time.max)
        ) + timedelta(hours=grace_hours)
        if timezone.now() > deadline:
            return responses.BadRequestError(
                details="Submission window has closed"
            ).get_response()

        task.submit(
            proof_link=validated_data.get("proof_link"),
            proof_file=validated_data.get("proof_file"),
            note=validated_data.get("note"),
        )

        data = self.serializer_class(task, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    def get_task(self, uuid):
        return models.MemberTask.objects.filter(
            uuid=uuid, member_job__member__uuid=self.kwargs.get("member_uuid"),
        ).first()

    @extend_schema(request=serializers_create.TaskContentSerializer)
    @action(detail=True, methods=["post"])
    def content(self, request, uuid=None, *args, **kwargs):
        """The finished reel / photo files for this task."""
        serializer = serializers_create.TaskContentSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        task = self.get_task(uuid)
        if task is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        for upload in serializer.validated_data["files"]:
            models.TaskFile.objects.create(
                task=task,
                file=upload,
                media_type=helper_functions.media_type_for(upload.name),
                original_name=upload.name[:255],
                size=upload.size,
            )

        data = self.serializer_class(task, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @action(detail=True, methods=["patch"], url_path=r"content/(?P<file_uuid>[^/.]+)")
    def remove_content(self, request, uuid=None, file_uuid=None, *args, **kwargs):
        task = self.get_task(uuid)
        if task is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        task_file = task.files.filter(uuid=file_uuid).first()
        if task_file is None:
            return responses.MissingItemError(
                item_key="Task File Id", item_id=file_uuid,
            ).get_response()

        if task_file.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key="Task File Id", item_id=file_uuid,
            ).get_response()

        task_file.archive()

        data = self.serializer_class(task, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.TaskResultSerializer)
    @action(detail=True, methods=["post", "patch"])
    def result(self, request, uuid=None, *args, **kwargs):
        """How the post performed.

        No submission deadline here: views only accumulate after posting,
        so this is filled in days later.
        """
        serializer = serializers_create.TaskResultSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        task = self.get_task(uuid)
        if task is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if not task.is_submitted:
            return responses.BadRequestError(
                details="Submit the task before reporting its result"
            ).get_response()

        task.submit_result(**serializer.validated_data)

        data = self.serializer_class(task, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()
