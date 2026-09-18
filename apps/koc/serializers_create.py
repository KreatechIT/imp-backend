from rest_framework import serializers

from core import encryption


class SubmissionCreateSerializer(serializers.Serializer):
    content_file = serializers.FileField(
        required=True,
        validators=[encryption.validate_content_file_size],
    )
    published_url = serializers.URLField(required=True, max_length=500)
