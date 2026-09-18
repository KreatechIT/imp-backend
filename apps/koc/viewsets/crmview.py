from django.db.models import Q
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.koc import models, serializers_create, serializers_get
from core import permissions
from core.pagination import StandardPagination


class AdminSubmissionViewSet(ReadOnlyModelViewSet):
    """Admin review of all KOC Published Reel Link submissions."""

    serializer_class = serializers_get.AdminSubmissionSerializer
    permission_classes = [permissions.IsAdmin]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Submission Id"

    def get_queryset(self):
        query = serializers_create.SubmissionFilterSerializer(
            data=self.request.query_params,
        )
        query.is_valid(raise_exception=True)
        filters = query.validated_data

        queryset = (
            models.Submission.objects
            .select_related("member__user")
            .order_by("-created")
        )

        if filters.get("member_uuid"):
            queryset = queryset.filter(member__uuid=filters["member_uuid"])
        if filters.get("search"):
            term = filters["search"]
            queryset = queryset.filter(
                Q(member__full_name__icontains=term)
                | Q(member__user__username__icontains=term)
                | Q(member__phone_number__icontains=term)
                | Q(published_url__icontains=term)
            )
        if filters.get("from_date"):
            queryset = queryset.filter(created__date__gte=filters["from_date"])
        if filters.get("to_date"):
            queryset = queryset.filter(created__date__lte=filters["to_date"])
        if filters.get("platform"):
            queryset = queryset.filter(platform=filters["platform"])
        return queryset
