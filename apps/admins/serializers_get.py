from rest_framework import serializers

from apps.admins import models


class AdminSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")
    status = serializers.CharField(source="get_status_display")
    last_login = serializers.DateTimeField(source="user.last_login")

    class Meta:
        model = models.Admin
        fields = [
            "uuid",
            "username",
            "full_name",
            "status",
            "profile_picture",
            "last_login",
            "created",
        ]


class ActivityLogSerializer(serializers.ModelSerializer):
    datetime = serializers.DateTimeField(source="created")
    admin = serializers.CharField(source="admin.user.username")

    class Meta:
        model = models.ActivityLog
        fields = [
            "uuid",
            "datetime",
            "admin",
            "activity",
        ]
