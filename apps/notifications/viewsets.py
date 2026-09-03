from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.notifications import models, serializers_get
from base import responses
from core import permissions
from core.pagination import StandardPagination


class NotificationViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    lookup_field = "uuid"
    item_key = "Notification Id"

    def get_queryset(self):
        queryset = models.Notification.objects.filter(recipient=self.request.user)
        unread_only = self.request.query_params.get("unread")
        if unread_only in ("1", "true", "True"):
            queryset = queryset.filter(read_at__isnull=True)
        return queryset

    @action(detail=False, methods=["get"])
    def unread_count(self, request, *args, **kwargs):
        count = self.get_queryset().filter(read_at__isnull=True).count()
        return responses.SuccessResponse(data={"count": count}).get_response()

    @action(detail=True, methods=["patch"])
    def read(self, request, uuid=None, *args, **kwargs):
        notification = self.get_queryset().filter(uuid=uuid).first()
        if notification is None:
            return responses.MissingItemError(
                item_key=self.item_key, item_id=uuid,
            ).get_response()

        notification.mark_read()

        data = self.serializer_class(notification).data
        return responses.SuccessResponse(data=data).get_response()

    @action(detail=False, methods=["patch"], url_path="read-all")
    def read_all(self, request, *args, **kwargs):
        self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return responses.SuccessResponse(data={"count": 0}).get_response()
