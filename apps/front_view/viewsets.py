from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
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
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Banner Id"

    def get_queryset(self):
        queryset = models.Banner.objects.filter(archived=None)
        location = self.request.query_params.get("location")
        if location:
            queryset = queryset.filter(location=location)
        return queryset.order_by("location", "ordering", "-created")

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
    permission_classes = [permissions.IsAdmin]
    lookup_field = "uuid"
    item_key = "Guide Id"

    def get_queryset(self):
        queryset = models.Guide.objects.filter(archived=None)
        location = self.request.query_params.get("location")
        if location:
            queryset = queryset.filter(location=location)
        return queryset.order_by("location", "ordering", "created")

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
    serializer_class = serializers_get.TermsAndConditionsSerializer
    permission_classes = [permissions.IsAdmin]
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


class ContentViewSet(ReadOnlyModelViewSet):
    """Everything a member's screens read: live banners, guides and terms."""

    serializer_class = serializers_get.BannerSerializer
    permission_classes = [permissions.IsMember]
    lookup_field = "uuid"

    def get_queryset(self):
        now = timezone.now()
        queryset = (
            models.Banner.objects
            .filter(archived=None)
            .filter(Q(active_from__isnull=True) | Q(active_from__lte=now))
            .filter(Q(active_until__isnull=True) | Q(active_until__gte=now))
        )
        location = self.request.query_params.get("location")
        if location:
            queryset = queryset.filter(location=location)
        return queryset.order_by("location", "ordering", "-created")

    @action(detail=False, methods=["get"])
    def guides(self, request, *args, **kwargs):
        queryset = models.Guide.objects.filter(archived=None)
        location = request.query_params.get("location")
        if location:
            queryset = queryset.filter(location=location)
        queryset = queryset.order_by("location", "ordering", "created")

        data = serializers_get.GuideSerializer(
            queryset, many=True, context={"request": self.request},
        ).data
        return responses.SuccessResponse(data=data).get_response()

    @action(detail=False, methods=["get"], url_path="terms")
    def terms(self, request, *args, **kwargs):
        queryset = models.TermsAndConditions.objects.all().order_by("category")
        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)

        data = serializers_get.TermsAndConditionsSerializer(
            queryset, many=True, context={"request": self.request},
        ).data
        return responses.SuccessResponse(data=data).get_response()
