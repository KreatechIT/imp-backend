from rest_framework import serializers

from apps.frames import models
from apps.jobs.models import TaskFile


class OriginalContentSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="task.member_job.member.full_name")
    member_uuid = serializers.UUIDField(source="task.member_job.member.uuid")
    job_uuid = serializers.UUIDField(source="task.member_job.job.uuid")
    job_title = serializers.CharField(source="task.member_job.job.title")
    task_uuid = serializers.UUIDField(source="task.uuid")
    frame_uuid = serializers.UUIDField(source="frame.uuid")
    frame_name = serializers.CharField(source="frame.name")

    class Meta:
        model = TaskFile
        fields = [
            "uuid",
            "member",
            "member_uuid",
            "job_uuid",
            "job_title",
            "task_uuid",
            "frame_uuid",
            "frame_name",
            "file",
            "media_type",
            "original_name",
            "size",
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
