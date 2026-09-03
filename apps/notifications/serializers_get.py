from rest_framework import serializers

from apps.notifications import models


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField()

    class Meta:
        model = models.Notification
        fields = [
            "uuid",
            "notification_type",
            "title",
            "message",
            "is_read",
            "read_at",
            "created",
        ]
