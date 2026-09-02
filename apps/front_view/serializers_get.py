from rest_framework import serializers

from apps.front_view import models


class BannerSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Banner
        fields = [
            "uuid",
            "name",
            "image",
            "link",
            "location",
            "active_from",
            "active_until",
            "ordering",
            "is_live",
            "created",
        ]


class GuideSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Guide
        fields = [
            "uuid",
            "location",
            "title",
            "content",
            "ordering",
            "modified",
        ]


class TermsAndConditionsSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TermsAndConditions
        fields = [
            "uuid",
            "category",
            "content",
            "modified",
        ]


class SingleTermsAndConditionsSerializer(serializers.ModelSerializer):
    """Flat shape for the public/<category>/ lookup — content only."""

    class Meta:
        model = models.TermsAndConditions
        fields = ["content"]
