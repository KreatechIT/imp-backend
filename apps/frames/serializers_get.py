from rest_framework import serializers

from apps.frames import models


class RenderedContentSerializer(serializers.ModelSerializer):
    member_uuid = serializers.UUIDField(source="member.uuid")
    member = serializers.CharField(source="member.full_name")
    job_uuid = serializers.UUIDField(source="frame.job.uuid")
    job_title = serializers.CharField(source="frame.job.title")
    frame_uuid = serializers.UUIDField(source="frame.uuid")
    frame_name = serializers.CharField(source="frame.name")

    class Meta:
        model = models.RenderedContent
        fields = [
            "uuid",
            "member",
            "member_uuid",
            "job_uuid",
            "job_title",
            "frame_uuid",
            "frame_name",
            "original_file",
            "rendered_file",
            "media_type",
            "original_name",
            "render_status",
            "created",
        ]


class FrameSerializer(serializers.ModelSerializer):
    job_uuid = serializers.UUIDField(source="job.uuid")
    job_title = serializers.CharField(source="job.title")
    org = serializers.CharField(source="job.company.name")

    class Meta:
        model = models.Frame
        fields = [
            "uuid",
            "job_uuid",
            "job_title",
            "org",
            "name",
            "image",
            "aspect_ratio",
            "media_type",
            "ordering",
            "status",
            "is_live",
            "created",
            "modified",
        ]
