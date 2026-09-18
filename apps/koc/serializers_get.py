from rest_framework import serializers

from apps.koc import models


class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Submission
        fields = [
            "uuid",
            "content_file",
            "media_type",
            "published_url",
            "created",
        ]


class AdminSubmissionSerializer(serializers.ModelSerializer):
    member_uuid = serializers.UUIDField(source="member.uuid")
    member_name = serializers.CharField(source="member.full_name")
    member_phone_number = serializers.CharField(source="member.phone_number")

    class Meta:
        model = models.Submission
        fields = [
            "uuid",
            "member_uuid",
            "member_name",
            "member_phone_number",
            "content_file",
            "media_type",
            "published_url",
            "created",
        ]
