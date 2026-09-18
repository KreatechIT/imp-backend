from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.frames import choices, models, serializers_create, serializers_get
from apps.frames.tasks import pull_source_video, render_content
from apps.jobs.helper_functions import media_type_for
from apps.third_party.models import ThirdPartyConnection
from base import responses
from base.utils import log_action
from core import permissions
from core.pagination import StandardPagination


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


class MemberPostDeskFrameViewSet(ReadOnlyModelViewSet):
    """The frames a KOC can apply to their own content, no job involved."""

    serializer_class = serializers_get.FrameSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Frame Id"

    def get_queryset(self):
        member = getattr(self.request.user, "member", None)
        if member is None:
            return models.Frame.objects.none()

        return models.Frame.objects.filter(
            assignments__archived=None,
            status=1,
            archived=None,
            frame_type=2,
        ).filter(
            Q(assignments__member=member) | Q(assignments__user_group__members=member),
        ).order_by("ordering", "created").distinct()


class SourceVideoViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.SourceVideoSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Source Video Id"

    def get_member(self):
        return getattr(self.request.user, "member", None)

    def get_queryset(self):
        member = self.get_member()
        if member is None:
            return models.SourceVideo.objects.none()

        member_uuid = self.kwargs.get("member_uuid")
        cutoff = timezone.now() - timedelta(hours=choices.SOURCE_VIDEO_VISIBILITY_HOURS)
        return (
            models.SourceVideo.objects
            .filter(member=member, member__uuid=member_uuid, created__gte=cutoff)
            .order_by("-created")
        )

    @staticmethod
    def get_active_source_video(member, uuid):
        cutoff = timezone.now() - timedelta(hours=choices.SOURCE_VIDEO_VISIBILITY_HOURS)
        return models.SourceVideo.objects.filter(
            uuid=uuid, member=member, created__gte=cutoff,
        ).first()

    @extend_schema(request=serializers_create.UploadSourceVideoSerializer)
    @action(detail=False, methods=["post"], url_path="upload")
    def upload(self, request, *args, **kwargs):
        serializer = serializers_create.UploadSourceVideoSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        member = self.get_member()
        if member is None:
            return responses.MissingItemError(
                item_key="Member Id", item_id=str(request.user.id),
            ).get_response()

        upload = serializer.validated_data["file"]

        source_video = models.SourceVideo.objects.create(
            member=member,
            original_file=upload,
            media_type=media_type_for(upload.name),
            original_name=upload.name[:255],
            pull_status=2,
        )

        log_action(
            actor=request.user,
            action="source_video.uploaded",
            target=source_video,
            detail=f"{member} uploaded video {source_video.original_name}",
        )

        data = self.serializer_class(source_video, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.PullSourceVideoSerializer)
    @action(detail=False, methods=["post"], url_path="pull")
    def pull(self, request, *args, **kwargs):
        serializer = serializers_create.PullSourceVideoSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated = serializer.validated_data

        member = self.get_member()
        if member is None:
            return responses.MissingItemError(
                item_key="Member Id", item_id=str(request.user.id),
            ).get_response()

        connection = ThirdPartyConnection.objects.filter(
            uuid=validated["connection_uuid"], member=member, archived=None,
        ).first()
        if connection is None:
            return responses.MissingItemError(
                item_key="Connection Id", item_id=validated["connection_uuid"],
            ).get_response()
        if connection.is_expired:
            return responses.BadRequestError(
                error_message="This connection has expired — reconnect the account and try again.",
            ).get_response()

        source_video = models.SourceVideo.objects.create(
            member=member,
            connection=connection,
            source_url=validated["source_url"],
            pull_status=1,
        )

        pull_source_video.delay(source_video.id)

        log_action(
            actor=request.user,
            action="source_video.pull_requested",
            target=source_video,
            detail=f"{member} requested a video pull from {connection}",
        )

        data = self.serializer_class(source_video, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()


class FrameRenderViewSet(ReadOnlyModelViewSet):
    """The Frame Editor: import content, apply a frame, export the result.

    Addressed by frame uuid alone - a frame already knows which job it
    belongs to, so no job/org/task uuid is needed in the path.
    """

    serializer_class = serializers_get.RenderDetailSerializer
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

        source_video = models.SourceVideo.objects.create(
            member=member,
            original_file=upload,
            media_type=media_type_for(upload.name),
            original_name=upload.name[:255],
            pull_status=2,
        )

        rendered = models.RenderedContent.objects.create(
            source_video=source_video,
            frame=frame,
            member=member,
            crop_x=serializer.validated_data.get("crop_x"),
            crop_y=serializer.validated_data.get("crop_y"),
            crop_width=serializer.validated_data.get("crop_width"),
            crop_height=serializer.validated_data.get("crop_height"),
            trim_in=serializer.validated_data.get("trim_in"),
            trim_out=serializer.validated_data.get("trim_out"),
        )

        render_content.delay(rendered.id)

        log_action(
            actor=request.user,
            action="rendered_content.generated",
            target=rendered,
            detail=f"{member} generated a render for frame {frame}",
        )

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

        log_action(
            actor=request.user,
            action="rendered_content.downloaded",
            target=rendered,
            detail=f"{rendered.member} downloaded render for frame {rendered.frame}",
        )

        data = self.serializer_class(rendered, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class PostDeskRenderViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.RenderDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Render Id"

    def get_queryset(self):
        return (
            models.RenderedContent.objects
            .filter(
                source_video__uuid=self.kwargs.get("source_video_uuid"),
                member__user=self.request.user,
                member__uuid=self.kwargs.get("member_uuid"),
            )
            .select_related("member__user", "frame", "source_video")
            .order_by("-created")
        )

    def get_allowed_frame(self, frame_uuid, member):
        frame = models.Frame.objects.filter(
            uuid=frame_uuid, archived=None, frame_type=2,
        ).first()
        if frame is None:
            return None

        allowed = models.FrameAssignment.objects.filter(
            frame=frame, archived=None,
        ).filter(Q(member=member) | Q(user_group__members=member)).exists()

        return frame if allowed else None

    @extend_schema(request=serializers_create.PostDeskRenderRequestSerializer)
    def create(self, request, member_uuid=None, source_video_uuid=None, *args, **kwargs):
        serializer = serializers_create.PostDeskRenderRequestSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        member = getattr(request.user, "member", None)
        if member is None or str(member.uuid) != member_uuid:
            return responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        frame = self.get_allowed_frame(serializer.validated_data["frame_uuid"], member)
        if frame is None:
            return responses.MissingItemError(
                item_key="Frame Id", item_id=str(serializer.validated_data["frame_uuid"]),
            ).get_response()

        source_video = SourceVideoViewSet.get_active_source_video(member, source_video_uuid)
        if source_video is None:
            return responses.MissingItemError(
                item_key="Source Video Id", item_id=source_video_uuid,
            ).get_response()
        if source_video.pull_status != 2:
            return responses.BadRequestError(
                error_message="This video isn't ready yet.",
            ).get_response()

        rendered = models.RenderedContent.objects.create(
            source_video=source_video,
            frame=frame,
            member=member,
            crop_x=serializer.validated_data.get("crop_x"),
            crop_y=serializer.validated_data.get("crop_y"),
            crop_width=serializer.validated_data.get("crop_width"),
            crop_height=serializer.validated_data.get("crop_height"),
            trim_in=serializer.validated_data.get("trim_in"),
            trim_out=serializer.validated_data.get("trim_out"),
            caption_text=serializer.validated_data.get("caption_text", ""),
            caption_color=serializer.validated_data.get("caption_color", ""),
            caption_background_color=serializer.validated_data.get("caption_background_color", ""),
            caption_font_size=serializer.validated_data.get("caption_font_size"),
            caption_x=serializer.validated_data.get("caption_x"),
            caption_y=serializer.validated_data.get("caption_y"),
            caption_reference_height=serializer.validated_data.get("caption_reference_height"),
            overlay_x=serializer.validated_data.get("overlay_x"),
            overlay_y=serializer.validated_data.get("overlay_y"),
            overlay_zoom=serializer.validated_data.get("overlay_zoom"),
        )

        render_content.delay(rendered.id)

        log_action(
            actor=request.user,
            action="rendered_content.generated",
            target=rendered,
            detail=f"{member} generated a PostDesk render for frame {frame}",
        )

        data = self.serializer_class(rendered, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @action(detail=True, methods=["post"])
    def downloaded(self, request, uuid=None, member_uuid=None, source_video_uuid=None, *args, **kwargs):
        rendered = self.get_queryset().filter(uuid=uuid).first()
        if rendered is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if rendered.rendered_file:
            rendered.rendered_file.delete(save=False)
            rendered.rendered_file = None
            rendered.save()

        log_action(
            actor=request.user,
            action="rendered_content.downloaded",
            target=rendered,
            detail=f"{rendered.member} downloaded PostDesk render for frame {rendered.frame}",
        )

        data = self.serializer_class(rendered, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()
