from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.koc import models, serializers_get
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
        queryset = (
            models.Submission.objects
            .select_related("member__user")
            .order_by("-created")
        )

        member_uuid = self.request.query_params.get("member_uuid")
        from_date = self.request.query_params.get("from_date")
        to_date = self.request.query_params.get("to_date")
        platform = self.request.query_params.get("platform")

        if member_uuid:
            queryset = queryset.filter(member__uuid=member_uuid)
        if from_date:
            queryset = queryset.filter(created__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(created__date__lte=to_date)
        if platform:
            queryset = queryset.filter(platform=platform)
        return queryset
