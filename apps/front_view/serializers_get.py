from rest_framework import serializers

from apps.front_view import models


class BannerSerializer(serializers.ModelSerializer):
    location = serializers.CharField(source="get_location_display")
    location_code = serializers.IntegerField(source="location")

    class Meta:
        model = models.Banner
        fields = [
            "uuid",
            "name",
            "image",
            "link",
            "location",
            "location_code",
            "active_from",
            "active_until",
            "ordering",
            "is_live",
            "created",
        ]


class GuideSerializer(serializers.ModelSerializer):
    location = serializers.CharField(source="get_location_display")
    location_code = serializers.IntegerField(source="location")

    class Meta:
        model = models.Guide
        fields = [
            "uuid",
            "location",
            "location_code",
            "title",
            "content",
            "ordering",
            "modified",
        ]


class TermsAndConditionsSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="get_category_display")
    category_code = serializers.IntegerField(source="category")

    class Meta:
        model = models.TermsAndConditions
        fields = [
            "uuid",
            "category",
            "category_code",
            "content",
            "modified",
        ]
