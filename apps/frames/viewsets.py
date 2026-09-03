from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.frames import models, serializers_create, serializers_get
from apps.jobs.models import Job
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
            job__uuid=self.kwargs.get("job_uuid"), archived=None,
        ).select_related("job__company")

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
            uuid=uuid, job__uuid=self.kwargs.get("job_uuid"),
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

        frame = models.Frame.objects.create(job=job, **serializer.validated_data)

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
            archived=None,
        ).select_related("job__company")

        job_uuid = self.request.query_params.get("job_uuid")
        media_type = self.request.query_params.get("media_type")
        status = self.request.query_params.get("status")
        if job_uuid:
            queryset = queryset.filter(job__uuid=job_uuid)
        if media_type:
            queryset = queryset.filter(media_type__in=[1, media_type])
        if status:
            queryset = queryset.filter(status=status)
        return queryset.order_by("ordering", "created")

    def get_frame(self, uuid):
        return models.Frame.objects.filter(uuid=uuid).first()

    @extend_schema(request=serializers_create.FrameSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.FrameSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        validated_data = serializer.validated_data

        job_uuid = validated_data.pop("job_uuid")
        job = Job.objects.filter(uuid=job_uuid, archived=None).first()
        if job is None:
            return responses.MissingItemError(
                item_key="Job Id", item_id=job_uuid,
            ).get_response()

        frame = models.Frame.objects.create(job=job, **validated_data)

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
        job_uuid = validated_data.pop("job_uuid", None)
        if job_uuid:
            job = Job.objects.filter(uuid=job_uuid, archived=None).first()
            if job is None:
                return responses.MissingItemError(
                    item_key="Job Id", item_id=job_uuid,
                ).get_response()
            validated_data["job"] = job

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


class FrameByJobViewSet(ReadOnlyModelViewSet):
    """List-only: frames belonging to one job."""

    serializer_class = serializers_get.FrameSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Frame Id"

    def get_queryset(self):
        queryset = models.Frame.objects.filter(
            job__uuid=self.kwargs.get("job_uuid"), archived=None,
        ).select_related("job__company")

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
            job__uuid=self.kwargs.get("job_uuid"),
            job__member_jobs__member__uuid=self.kwargs.get("member_uuid"),
            job__member_jobs__status=2,
            job__member_jobs__archived=None,
            status=1,
            archived=None,
        ).select_related("job__company").distinct()

        media_type = self.request.query_params.get("media_type")
        aspect_ratio = self.request.query_params.get("aspect_ratio")
        if media_type:
            queryset = queryset.filter(media_type__in=[1, media_type])
        if aspect_ratio:
            queryset = queryset.filter(aspect_ratio=aspect_ratio)
        return queryset.order_by("ordering", "created")
