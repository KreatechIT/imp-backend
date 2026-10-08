from datetime import datetime, time

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.front_view import models, serializers_create, serializers_get
from base import responses
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


class DummyInfluencerViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.DummyInfluencerSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Dummy Influencer Id"

    def get_queryset(self):
        return models.DummyInfluencer.objects.filter(
            archived=None,
        ).order_by("-deposit_amount", "-created")

    @extend_schema(request=serializers_create.DummyInfluencerSerializer)
    def create(self, request, *args, **kwargs):
        serializer = serializers_create.DummyInfluencerSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        dummy = models.DummyInfluencer.objects.create(**serializer.validated_data)

        data = self.serializer_class(dummy).data
        return responses.CreatedSuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditDummyInfluencerSerializer)
    def update(self, request, uuid=None, *args, **kwargs):
        serializer = serializers_create.EditDummyInfluencerSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        try:
            dummy = models.DummyInfluencer.objects.get(uuid=uuid)
        except models.DummyInfluencer.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if dummy.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        dummy.update(**serializer.validated_data)

        data = self.serializer_class(dummy).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.EditDummyInfluencerSerializer)
    def partial_update(self, request, uuid=None, *args, **kwargs):
        return self.update(request, uuid=uuid, *args, **kwargs)

    @action(detail=True, methods=["patch"])
    def archive(self, request, uuid=None, *args, **kwargs):
        try:
            dummy = models.DummyInfluencer.objects.get(uuid=uuid)
        except models.DummyInfluencer.DoesNotExist:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        if dummy.is_archived:
            return responses.ItemAlreadyArchivedError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        dummy.archive()

        data = self.serializer_class(dummy).data
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


def parse_bound(value, end_of_day):
    """An ISO datetime, or a plain date meaning the start/end of that day."""
    day = parse_date(value)
    if day is not None:
        parsed = datetime.combine(day, time.max if end_of_day else time.min)
    else:
        parsed = parse_datetime(value)
        if parsed is None:
            raise ValueError(value)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


class InfluencerSyncRunViewSet(ReadOnlyModelViewSet):
    """History of the scheduled influencer syncs, newest first. Filter with
    ?date_from=&date_to= (date or datetime), ?status= and ?slot=. The detail
    view carries that run's full ranking."""

    serializer_class = serializers_get.InfluencerSyncRunSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Influencer Sync Run Id"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers_get.InfluencerSyncRunDetailSerializer
        return self.serializer_class

    def get_queryset(self):
        queryset = models.InfluencerSyncRun.objects.prefetch_related("rows")
        params = self.request.query_params
        for key in ("status", "slot"):
            if params.get(key):
                queryset = queryset.filter(**{key: params[key]})
        if params.get("date_from"):
            queryset = queryset.filter(
                created__gte=parse_bound(params["date_from"], end_of_day=False),
            )
        if params.get("date_to"):
            queryset = queryset.filter(
                created__lte=parse_bound(params["date_to"], end_of_day=True),
            )
        return queryset.order_by("-created")

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except ValueError:
            return responses.BadRequestError(
                details="Use an ISO date or datetime for date_from and date_to",
            ).get_response()
