from django.db import transaction
from django.db.models import Count, Prefetch, Q
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.frames import models, serializers_create, serializers_get
from apps.jobs.models import Job
from apps.members.models import Member, UserGroup
from base import responses
from core import permissions
from core.pagination import StandardPagination


class FrameViewSet(ReadOnlyModelViewSet):
    """Admin frame library for one job."""

    serializer_class = serializers_get.FrameSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Frame Id"

    def get_queryset(self):
        queryset = models.Frame.objects.filter(
            assignments__job__uuid=self.kwargs.get("job_uuid"),
            assignments__archived=None,
            archived=None,
            frame_type=1,
        ).prefetch_related("assignments__job__company").distinct()

        media_type = self.request.query_params.get("media_type")
        status = self.request.query_params.get("status")
        if media_type:
            queryset = queryset.filter(media_type__in=[1, media_type])
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by("ordering", "created")

    def get_job(self):
        return Job.objects.filter(
            uuid=self.kwargs.get("job_uuid"), archived=None,
        ).first()

    def get_frame(self, uuid):
        return models.Frame.objects.filter(
            uuid=uuid,
            assignments__job__uuid=self.kwargs.get("job_uuid"),
            assignments__archived=None,
        ).first()

    @extend_schema(request=serializers_create.FrameSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.FrameSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        job = self.get_job()
        if job is None:
            return responses.MissingItemError(
                item_key="Job Id", item_id=self.kwargs.get("job_uuid"),
            ).get_response()

        validated_data = dict(serializer.validated_data)
        validated_data.pop("job_uuid", None)
        validated_data.pop("members", None)
        validated_data.pop("user_groups", None)
        validated_data["frame_type"] = 1
        frame = models.Frame.objects.create(**validated_data)
        models.FrameAssignment.objects.create(frame=frame, job=job)

        data = self.serializer_class(frame, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditFrameSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditFrameSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        frame = self.get_frame(uuid)
        if frame is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if frame.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        frame.update(**serializer.validated_data)

        data = self.serializer_class(frame, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditFrameSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        frame = self.get_frame(uuid)
        if frame is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if frame.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        frame.archive()

        data = self.serializer_class(frame, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class FrameLibraryViewSet(ModelViewSet):
    """Full frame library across all jobs, addressed by frame uuid."""

    serializer_class = serializers_get.FrameSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Frame Id"

    def get_queryset(self):
        queryset = models.Frame.objects.filter(
            archived=None, frame_type=1,
        ).prefetch_related("assignments__job__company").distinct()

        job_uuid = self.request.query_params.get("job_uuid")
        media_type = self.request.query_params.get("media_type")
        status = self.request.query_params.get("status")
        if job_uuid:
            queryset = queryset.filter(
                assignments__job__uuid=job_uuid, assignments__archived=None,
            )
        if media_type:
            queryset = queryset.filter(media_type__in=[1, media_type])
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by("ordering", "created")

    def get_frame(self, uuid):
        return models.Frame.objects.filter(uuid=uuid).first()

    def resolve_targets(self, member_uuids, group_uuids):
        members = list(Member.objects.filter(uuid__in=member_uuids, archived=None))
        groups = list(UserGroup.objects.filter(uuid__in=group_uuids, archived=None))

        found = {str(member.uuid) for member in members}
        found |= {str(group.uuid) for group in groups}
        missing = [
            str(uuid) for uuid in list(member_uuids) + list(group_uuids)
            if str(uuid) not in found
        ]
        return members, groups, missing

    def set_targets(self, frame, members, groups):
        frame.assignments.filter(job__isnull=True).delete()
        models.FrameAssignment.objects.bulk_create(
            [models.FrameAssignment(frame=frame, member=m) for m in members]
            + [models.FrameAssignment(frame=frame, user_group=g) for g in groups]
        )

    @extend_schema(request=serializers_create.FrameSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.FrameSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = dict(serializer.validated_data)

        job_uuid = validated_data.pop("job_uuid", None)
        member_uuids = validated_data.pop("members", [])
        group_uuids = validated_data.pop("user_groups", [])

        job = None
        members, groups = [], []
        if validated_data["frame_type"] == 1:
            job = Job.objects.filter(uuid=job_uuid, archived=None).first()
            if job is None:
                return responses.MissingItemError(
                    item_key="Job Id", item_id=job_uuid,
                ).get_response()
        else:
            members, groups, missing = self.resolve_targets(
                member_uuids, group_uuids,
            )
            if missing:
                return responses.MissingItemError(
                    item_key="Assignment Id", item_id=", ".join(missing),
                ).get_response()

        with transaction.atomic():
            frame = models.Frame.objects.create(**validated_data)
            if job is not None:
                models.FrameAssignment.objects.create(frame=frame, job=job)
            else:
                self.set_targets(frame, members, groups)

        data = self.serializer_class(frame, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditFrameSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditFrameSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        frame = self.get_frame(uuid)
        if frame is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if frame.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        validated_data = dict(serializer.validated_data)
        validated_data.pop("frame_type", None)
        job_uuid = validated_data.pop("job_uuid", None)
        reassign = "members" in validated_data or "user_groups" in validated_data
        member_uuids = validated_data.pop("members", [])
        group_uuids = validated_data.pop("user_groups", [])

        if frame.frame_type == 1 and (reassign or validated_data.get("background")):
            return responses.BadRequestError(
                details="members, user_groups and background are not allowed on job frames",
            ).get_response()

        if frame.frame_type == 2 and job_uuid:
            return responses.BadRequestError(
                details="job_uuid is not allowed on PostDesk frames",
            ).get_response()

        job = None
        members, groups = [], []
        if job_uuid:
            job = Job.objects.filter(uuid=job_uuid, archived=None).first()
            if job is None:
                return responses.MissingItemError(
                    item_key="Job Id", item_id=job_uuid,
                ).get_response()

        if reassign:
            members, groups, missing = self.resolve_targets(
                member_uuids, group_uuids,
            )
            if missing:
                return responses.MissingItemError(
                    item_key="Assignment Id", item_id=", ".join(missing),
                ).get_response()

        with transaction.atomic():
            if job is not None:
                frame.assignments.filter(job__isnull=False).update(job=job)
            if reassign:
                self.set_targets(frame, members, groups)
            if validated_data:
                frame.update(**validated_data)

        data = self.serializer_class(frame, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditFrameSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    def destroy(self, request, uuid=None, *args, **kwargs):
        return self.archive(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        frame = self.get_frame(uuid)
        if frame is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if frame.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        frame.archive()

        data = self.serializer_class(frame, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class FramePostDeskViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.FrameDetailSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "PostDesk Frame Id"

    def get_queryset(self):
        assignments = models.FrameAssignment.objects.filter(
            archived=None,
        ).select_related("member__user", "user_group")

        queryset = (
            models.Frame.objects
            .filter(frame_type=2, archived=None)
            .annotate(
                total_assigned=Count(
                    "assignments",
                    filter=Q(assignments__archived__isnull=True),
                    distinct=True,
                ),
            )
            .prefetch_related(Prefetch("assignments", queryset=assignments))
        )

        name = self.request.query_params.get("name")
        status = self.request.query_params.get("status")
        if name:
            queryset = queryset.filter(name__icontains=name)
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by("-created")


class FrameByJobViewSet(ReadOnlyModelViewSet):
    """List-only: frames belonging to one job."""

    serializer_class = serializers_get.FrameSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Frame Id"

    def get_queryset(self):
        queryset = models.Frame.objects.filter(
            assignments__job__uuid=self.kwargs.get("job_uuid"),
            assignments__archived=None,
            archived=None,
            frame_type=1,
        ).prefetch_related("assignments__job__company").distinct()

        media_type = self.request.query_params.get("media_type")
        status = self.request.query_params.get("status")
        if media_type:
            queryset = queryset.filter(media_type__in=[1, media_type])
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by("ordering", "created")


class MemberFrameViewSet(ReadOnlyModelViewSet):
    """The frames the editor offers for a job the member is actually on."""

    serializer_class = serializers_get.FrameSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Frame Id"

    def get_queryset(self):
        # scoped through the member's own job, so a job they do not hold
        # simply yields nothing
        queryset = models.Frame.objects.filter(
            assignments__job__uuid=self.kwargs.get("job_uuid"),
            assignments__archived=None,
            assignments__job__member_jobs__member__uuid=self.kwargs.get("member_uuid"),
            assignments__job__member_jobs__status=2,
            assignments__job__member_jobs__archived=None,
            status=1,
            archived=None,
            frame_type=1,
        ).prefetch_related("assignments__job__company").distinct()

        media_type = self.request.query_params.get("media_type")
        aspect_ratio = self.request.query_params.get("aspect_ratio")
        if media_type:
            queryset = queryset.filter(media_type__in=[1, media_type])
        if aspect_ratio:
            queryset = queryset.filter(aspect_ratio=aspect_ratio)
        return queryset.order_by("ordering", "created")


class RenderedContentViewSet(ReadOnlyModelViewSet):
    """Admin library of raw content members uploaded to the Frame Editor."""

    serializer_class = serializers_get.RenderedContentSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Content Id"

    def get_queryset(self):
        queryset = (
            models.RenderedContent.objects
            .select_related("member__user", "frame")
            .prefetch_related("frame__assignments__job__company")
            .order_by("-created")
        )

        member_uuid = self.request.query_params.get("member_uuid")
        job_uuid = self.request.query_params.get("job_uuid")
        from_date = self.request.query_params.get("from_date")
        to_date = self.request.query_params.get("to_date")

        if member_uuid:
            queryset = queryset.filter(member__uuid=member_uuid)
        if job_uuid:
            queryset = queryset.filter(
                frame__assignments__job__uuid=job_uuid,
                frame__assignments__archived=None,
            )
        if from_date:
            queryset = queryset.filter(created__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(created__date__lte=to_date)
        return queryset

    def destroy(self, request, uuid=None, *args, **kwargs):
        rendered = self.get_queryset().filter(uuid=uuid).first()
        if rendered is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        rendered.original_file.delete(save=False)
        if rendered.rendered_file:
            rendered.rendered_file.delete(save=False)
        rendered.delete()

        return responses.SuccessResponse(data={}).get_response()


class FrameRenderViewSet(ReadOnlyModelViewSet):
    """The Frame Editor: import content, apply a frame, export the result.

    Addressed by frame uuid alone - a frame already knows which job it
    belongs to, so no job/org/task uuid is needed in the path.
    """

    serializer_class = serializers_get.RenderedContentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Render Id"

    def get_queryset(self):
        return (
            models.RenderedContent.objects
            .filter(
                frame__uuid=self.kwargs.get("frame_uuid"),
                member__user=self.request.user,
            )
            .select_related("member__user", "frame")
            .prefetch_related("frame__assignments__job__company")
            .order_by("-created")
        )

    def get_allowed_frame(self, frame_uuid, member):
        frame = models.Frame.objects.filter(uuid=frame_uuid, archived=None).first()
        if frame is None:
            return None

        assignments = models.FrameAssignment.objects.filter(
            frame=frame, archived=None,
        )
        if frame.frame_type == 1:
            allowed = assignments.filter(
                job__isnull=False,
                job__member_jobs__member=member,
                job__member_jobs__status=2,
                job__member_jobs__archived=None,
            ).exists()
        else:
            allowed = assignments.filter(
                Q(member=member) | Q(user_group__members=member),
            ).exists()

        return frame if allowed else None

    @extend_schema(request=serializers_create.RenderRequestSerializer)
    def create(self, request, frame_uuid=None, *args, **kwargs):
        serializer = serializers_create.RenderRequestSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        member = getattr(request.user, "member", None)
        if member is None:
            return responses.MissingItemError(
                item_key="Member Id", item_id=str(request.user.id),
            ).get_response()

        frame = self.get_allowed_frame(frame_uuid, member)
        if frame is None:
            return responses.MissingItemError(
                item_key="Frame Id", item_id=frame_uuid,
            ).get_response()

        upload = serializer.validated_data["file"]
        from apps.jobs.helper_functions import media_type_for

        rendered = models.RenderedContent.objects.create(
            frame=frame,
            member=member,
            original_file=upload,
            media_type=media_type_for(upload.name),
            original_name=upload.name[:255],
            crop_x=serializer.validated_data.get("crop_x"),
            crop_y=serializer.validated_data.get("crop_y"),
            crop_width=serializer.validated_data.get("crop_width"),
            crop_height=serializer.validated_data.get("crop_height"),
            trim_in=serializer.validated_data.get("trim_in"),
            trim_out=serializer.validated_data.get("trim_out"),
        )

        from apps.frames.tasks import render_content

        render_content.delay(rendered.id)

        data = self.serializer_class(rendered, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @action(detail=True, methods=["post"])
    def downloaded(self, request, uuid=None, frame_uuid=None, *args, **kwargs):
        rendered = self.get_queryset().filter(uuid=uuid).first()
        if rendered is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if rendered.rendered_file:
            rendered.rendered_file.delete(save=False)
            rendered.rendered_file = None
            rendered.save()

        data = self.serializer_class(rendered, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()
