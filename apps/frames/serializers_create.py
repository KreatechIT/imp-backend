from rest_framework import serializers

from apps.frames import choices
from core import encryption


class FrameSerializer(serializers.Serializer):
    frame_type = serializers.ChoiceField(
        choices=choices.FRAME_TYPE_CHOICES, default=1,
    )
    name = serializers.CharField(required=True)
    job_uuid = serializers.UUIDField(required=False)
    background = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[encryption.validate_file_size],
    )
    image = serializers.ImageField(
        required=False,
        allow_null=True,
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
    members = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True,
    )
    user_groups = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True,
    )

    def validate(self, attrs):
        errors = {}

        if attrs.get("frame_type", 1) == 1:
            if not attrs.get("job_uuid"):
                errors["job_uuid"] = "Required for job frames."
            if not attrs.get("image"):
                errors["image"] = "Required for job frames."
            if attrs.get("background"):
                errors["background"] = "Not allowed for job frames."
            if attrs.get("members") or attrs.get("user_groups"):
                errors["members"] = "Not allowed for job frames."
        else:
            if attrs.get("job_uuid"):
                errors["job_uuid"] = "Not allowed for PostDesk frames."
            if not attrs.get("background") and not attrs.get("image"):
                errors["background"] = "Provide a background, an overlay frame, or both."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class RenderRequestSerializer(serializers.Serializer):
    file = serializers.FileField(
        required=True,
        validators=[encryption.validate_content_file_size],
    )
    crop_x = serializers.IntegerField(required=False)
    crop_y = serializers.IntegerField(required=False)
    crop_width = serializers.IntegerField(required=False, min_value=1)
    crop_height = serializers.IntegerField(required=False, min_value=1)
    trim_in = serializers.FloatField(required=False, min_value=0)
    trim_out = serializers.FloatField(required=False, min_value=0)


class UploadSourceVideoSerializer(serializers.Serializer):
    file = serializers.FileField(
        required=True,
        validators=[encryption.validate_content_file_size],
    )


class PullSourceVideoSerializer(serializers.Serializer):
    connection_uuid = serializers.UUIDField(required=True)
    source_url = serializers.URLField(required=True)


class PostDeskRenderRequestSerializer(serializers.Serializer):
    frame_uuid = serializers.UUIDField(required=True)
    crop_x = serializers.IntegerField(required=False)
    crop_y = serializers.IntegerField(required=False)
    crop_width = serializers.IntegerField(required=False, min_value=1)
    crop_height = serializers.IntegerField(required=False, min_value=1)
    trim_in = serializers.FloatField(required=False, min_value=0)
    trim_out = serializers.FloatField(required=False, min_value=0)


class FrameSetupSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    background = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[encryption.validate_file_size],
    )
    image = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[
            encryption.validate_file_size,
            encryption.validate_transparent_image,
        ],
    )
    aspect_ratio = serializers.ChoiceField(
        choices=choices.ASPECT_RATIO_CHOICES, default=1,
    )
    status = serializers.ChoiceField(
        choices=choices.FRAME_STATUS_CHOICES, default=1,
    )
    members = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True,
    )
    user_groups = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True,
    )

    def validate(self, attrs):
        if not attrs.get("background") and not attrs.get("image"):
            raise serializers.ValidationError({
                "background": "Provide a background, an overlay frame, or both."
            })
        return attrs


class EditFrameSetupSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    background = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[encryption.validate_file_size],
    )
    image = serializers.ImageField(
        required=False,
        allow_null=True,
        validators=[
            encryption.validate_file_size,
            encryption.validate_transparent_image,
        ],
    )
    aspect_ratio = serializers.ChoiceField(
        choices=choices.ASPECT_RATIO_CHOICES, required=False,
    )
    status = serializers.ChoiceField(
        choices=choices.FRAME_STATUS_CHOICES, required=False,
    )
    members = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True,
    )
    user_groups = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True,
    )


class EditFrameSerializer(FrameSerializer):
    frame_type = serializers.ChoiceField(
        choices=choices.FRAME_TYPE_CHOICES, required=False,
    )
    name = serializers.CharField(required=False)
    job_uuid = serializers.UUIDField(required=False)
    image = serializers.ImageField(
        required=False,
        allow_null=True,
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

    def validate(self, attrs):
        return attrs
