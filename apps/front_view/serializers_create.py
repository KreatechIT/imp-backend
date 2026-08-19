from rest_framework import serializers

from apps.front_view import choices
from base.serializers import SanitizedHTMLField


class BannerSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    image = serializers.ImageField(required=False, allow_null=True)
    link = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    location = serializers.ChoiceField(
        choices=choices.BANNER_LOCATION_CHOICES, default=1,
    )
    active_from = serializers.DateTimeField(required=False, allow_null=True)
    active_until = serializers.DateTimeField(required=False, allow_null=True)
    ordering = serializers.IntegerField(required=False, min_value=0, default=0)

    def validate(self, attrs):
        active_from = attrs.get("active_from")
        active_until = attrs.get("active_until")
        if active_from and active_until and active_until < active_from:
            raise serializers.ValidationError({
                "active_until": "Active until cannot be before active from."
            })
        return attrs


class EditBannerSerializer(BannerSerializer):
    name = serializers.CharField(required=False)
    location = serializers.ChoiceField(
        choices=choices.BANNER_LOCATION_CHOICES, required=False,
    )
    ordering = serializers.IntegerField(required=False, min_value=0)


class GuideSerializer(serializers.Serializer):
    location = serializers.ChoiceField(
        choices=choices.GUIDE_LOCATION_CHOICES, required=True,
    )
    title = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
    )
    content = SanitizedHTMLField(required=True)
    ordering = serializers.IntegerField(required=False, min_value=0, default=0)


class EditGuideSerializer(serializers.Serializer):
    location = serializers.ChoiceField(
        choices=choices.GUIDE_LOCATION_CHOICES, required=False,
    )
    title = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
    )
    content = SanitizedHTMLField(required=False)
    ordering = serializers.IntegerField(required=False, min_value=0)


class TermsAndConditionsSerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=choices.TERMS_CATEGORY_CHOICES, required=True,
    )
    content = SanitizedHTMLField(required=True)


class EditTermsAndConditionsSerializer(serializers.Serializer):
    content = SanitizedHTMLField(required=True)
