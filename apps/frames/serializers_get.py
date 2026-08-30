from rest_framework import serializers

from apps.frames import models


class FrameSerializer(serializers.ModelSerializer):
    job_uuid = serializers.UUIDField(source="job.uuid")
    job_title = serializers.CharField(source="job.title")
    company = serializers.CharField(source="job.company.name")

    class Meta:
        model = models.Frame
        fields = [
            "uuid",
            "job_uuid",
            "job_title",
            "company",
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
