from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.front_view import models, serializers_create, serializers_get
from base import responses
from base.models import AuditLog
from core import permissions
from core.pagination import StandardPagination


class BannerViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.BannerSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Banner Id"

    def get_queryset(self):
        queryset = models.Banner.objects.filter(archived=None)
        location = self.request.query_params.get("location")
        if location:
            queryset = queryset.filter(location=location)
        return queryset.order_by("location", "ordering", "-created")

    @action(detail=False, methods=["get"])
    def public(self, request, *args, **kwargs):
        """Live banners — bare array, not paginated."""
        now = timezone.now()
        queryset = (
            models.Banner.objects
            .filter(archived=None)
            .filter(Q(active_from__isnull=True) | Q(active_from__lte=now))
            .filter(Q(active_until__isnull=True) | Q(active_until__gte=now))
        )
        location = request.query_params.get("location")
        if location is not None:
            try:
                location = int(location)
            except ValueError:
                return responses.BadRequestError(
                    details="Use an integer for this filter"
                ).get_response()
            queryset = queryset.filter(location=location)
        queryset = queryset.order_by("location", "ordering", "-created")

        data = self.serializer_class(
            queryset, many=True, context={"request": self.request},
        ).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.BannerSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.BannerSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        banner = models.Banner.objects.create(**serializer.validated_data)

        data = self.serializer_class(banner, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditBannerSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditBannerSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            banner = models.Banner.objects.get(uuid=uuid)
        except models.Banner.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if banner.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        banner.update(**serializer.validated_data)

        data = self.serializer_class(banner, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditBannerSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            banner = models.Banner.objects.get(uuid=uuid)
        except models.Banner.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if banner.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        banner.archive()

        data = self.serializer_class(banner, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class GuideViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.GuideSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    item_key = "Guide Id"

    def get_queryset(self):
        queryset = models.Guide.objects.filter(archived=None)
        location = self.request.query_params.get("location")
        if location:
            queryset = queryset.filter(location=location)
        return queryset.order_by("location", "ordering", "created")

    @action(detail=False, methods=["get"])
    def public(self, request, *args, **kwargs):
        """Guides — bare array, not paginated."""
        data = self.serializer_class(
            self.get_queryset(), many=True, context={"request": self.request},
        ).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.GuideSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.GuideSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        guide = models.Guide.objects.create(**serializer.validated_data)

        data = self.serializer_class(guide, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditGuideSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditGuideSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            guide = models.Guide.objects.get(uuid=uuid)
        except models.Guide.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if guide.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        guide.update(**serializer.validated_data)

        data = self.serializer_class(guide, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditGuideSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            guide = models.Guide.objects.get(uuid=uuid)
        except models.Guide.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if guide.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        guide.archive()

        data = self.serializer_class(guide, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()


class TermsAndConditionsViewSet(ReadOnlyModelViewSet):
    """List/create/update, and — since IsAuthenticated covers admin and
    member alike — this same GET list is also the member-facing read.
    A single category by itself is views.TermsPublicView, open with no
    auth at all, since a T&C page is often shown before login."""

    serializer_class = serializers_get.TermsAndConditionsSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    item_key = "Terms Id"

    def get_queryset(self):
        return models.TermsAndConditions.objects.all().order_by("category")

    @extend_schema(request=serializers_create.TermsAndConditionsSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.TermsAndConditionsSerializer(
            data=request.data
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            with transaction.atomic():
                terms = models.TermsAndConditions.objects.create(
                    **serializer.validated_data
                )
        except IntegrityError:
            return responses.ExistingDataError(
                item_key="Category",
                item_id=serializer.validated_data["category"],
            ).get_response()

        data = self.serializer_class(terms, context={"request": self.request}).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditTermsAndConditionsSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditTermsAndConditionsSerializer(
            data=request.data
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            terms = models.TermsAndConditions.objects.get(uuid=uuid)
        except models.TermsAndConditions.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        terms.update(**serializer.validated_data)

        data = self.serializer_class(terms, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditTermsAndConditionsSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)


class AuditLogViewSet(ReadOnlyModelViewSet):
    """Admin-only read of every action base.utils.log_action() recorded —
    KOC submissions, frame assignments, and anything else that calls it.
    Newest first.

    `target` is a GenericForeignKey, so it can't be select_related — the
    target objects for the current page are batch-fetched per content
    type in list()/retrieve() instead, one query per distinct target
    model rather than one query per row (and per row's own nested FKs,
    e.g. Submission.__str__ touching `member`).
    """

    serializer_class = serializers_get.AuditLogSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Audit Log Id"

    def get_queryset(self):
        query = serializers_create.AuditLogFilterSerializer(
            data=self.request.query_params,
        )
        query.is_valid(raise_exception=True)
        filters = query.validated_data

        queryset = (
            AuditLog.objects
            .select_related("actor__member", "actor__admin", "target_content_type")
            .order_by("-created")
        )

        # member_uuid may come from the query string (?member_uuid=...) or
        # from the path (log/member/<member_uuid>/) — either is accepted.
        member_uuid = filters.get("member_uuid") or self.kwargs.get("member_uuid")
        if member_uuid:
            queryset = queryset.filter(actor__member__uuid=member_uuid)
        if filters.get("action"):
            queryset = queryset.filter(action__icontains=filters["action"])
        if filters.get("from_date"):
            queryset = queryset.filter(created__date__gte=filters["from_date"])
        if filters.get("to_date"):
            queryset = queryset.filter(created__date__lte=filters["to_date"])
        return queryset

    @staticmethod
    def _attach_targets(logs):
        by_content_type = {}
        for log in logs:
            if log.target_content_type_id and log.target_object_id:
                by_content_type.setdefault(log.target_content_type_id, set()).add(
                    log.target_object_id
                )

        targets_by_key = {}
        for content_type_id, object_ids in by_content_type.items():
            content_type = ContentType.objects.get_for_id(content_type_id)
            model = content_type.model_class()
            if model is None:
                continue
            # str(target) commonly touches a `member` FK (Submission,
            # FrameAssignment, RenderedContent, MemberTask, etc.) —
            # select_related it, when the target model has one, so that
            # shared __str__ dependency doesn't cost one query per object.
            manager = model.objects
            if any(f.name == "member" for f in model._meta.get_fields()):
                manager = manager.select_related("member")
            for obj in manager.filter(pk__in=object_ids):
                targets_by_key[(content_type_id, str(obj.pk))] = obj

        for log in logs:
            key = (log.target_content_type_id, log.target_object_id)
            log._prefetched_target = targets_by_key.get(key)
        return logs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            self._attach_targets(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        logs = self._attach_targets(list(queryset))
        serializer = self.get_serializer(logs, many=True)
        return responses.SuccessResponse(data=serializer.data).get_response()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        self._attach_targets([instance])
        serializer = self.get_serializer(instance)
        return responses.SuccessResponse(data=serializer.data).get_response()
