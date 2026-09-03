from rest_framework import serializers

from apps.frames import choices
from core import encryption


class FrameSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    job_uuid = serializers.UUIDField(required=True)
    # Model validators only run on full_clean(), which objects.create()
    # skips, so the checks are repeated here where they actually fire.
    image = serializers.ImageField(
        required=True,
        validators=[
            encryption.validate_file_size,
            encryption.validate_transparent_image,
        ],
    )
    aspect_ratio = serializers.ChoiceField(
        choices=choices.ASPECT_RATIO_CHOICES, default=1,
    )
    media_type = serializers.ChoiceField(
        choices=choices.FRAME_MEDIA_TYPE_CHOICES, default=1,
    )
    ordering = serializers.IntegerField(required=False, min_value=0, default=0)
    status = serializers.ChoiceField(
        choices=choices.FRAME_STATUS_CHOICES, default=1,
    )


class EditFrameSerializer(FrameSerializer):
    name = serializers.CharField(required=False)
    job_uuid = serializers.UUIDField(required=False)
    image = serializers.ImageField(
        required=False,
        validators=[
            encryption.validate_file_size,
            encryption.validate_transparent_image,
        ],
    )
    aspect_ratio = serializers.ChoiceField(
        choices=choices.ASPECT_RATIO_CHOICES, required=False,
    )
    media_type = serializers.ChoiceField(
        choices=choices.FRAME_MEDIA_TYPE_CHOICES, required=False,
    )
    ordering = serializers.IntegerField(required=False, min_value=0)
    status = serializers.ChoiceField(
        choices=choices.FRAME_STATUS_CHOICES, required=False,
    )
