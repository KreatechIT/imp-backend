from rest_framework import serializers

from apps.third_party.choices import PROVIDER_CHOICES
from core import encryption


class SubmissionCreateSerializer(serializers.Serializer):
    content_file = serializers.FileField(
        required=True,
        validators=[encryption.validate_content_file_size],
    )
    platform = serializers.ChoiceField(choices=PROVIDER_CHOICES, required=True)
    published_url = serializers.URLField(required=True, max_length=500)


class SubmissionFilterSerializer(serializers.Serializer):
    member_uuid = serializers.UUIDField(required=False)
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    platform = serializers.ChoiceField(choices=PROVIDER_CHOICES, required=False)
