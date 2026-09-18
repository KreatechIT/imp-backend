from rest_framework import serializers

from apps.front_view import models
from base.models import AuditLog


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


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.SerializerMethodField()
    member_uuid = serializers.SerializerMethodField()
    member_name = serializers.SerializerMethodField()
    target_type = serializers.SerializerMethodField()
    target_label = serializers.SerializerMethodField()

    def get_actor_username(self, obj):
        return obj.actor.username if obj.actor else None

    def get_member_uuid(self, obj):
        member = getattr(obj.actor, "member", None) if obj.actor else None
        return member.uuid if member else None

    def get_member_name(self, obj):
        member = getattr(obj.actor, "member", None) if obj.actor else None
        return member.full_name if member else None

    def get_target_type(self, obj):
        return obj.target_content_type.model if obj.target_content_type else None

    def get_target_label(self, obj):
        target = getattr(obj, "_prefetched_target", None)
        return str(target) if target is not None else None

    class Meta:
        model = AuditLog
        fields = [
            "uuid",
            "created",
            "actor_username",
            "member_uuid",
            "member_name",
            "action",
            "status",
            "target_type",
            "target_label",
            "detail",
        ]
