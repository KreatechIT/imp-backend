from rest_framework import serializers

from apps.front_view import models
from apps.members.models import Member


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


class DummyInfluencerSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.DummyInfluencer
        fields = [
            "uuid",
            "full_name",
            "phone_number",
            "deposit_amount",
            "reg_count",
            "cvs_count",
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


class InfluencerSnapshotSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.InfluencerSnapshot
        fields = [
            "rank",
            "member_uuid",
            "full_name",
            "phone_number",
            "reg_count",
            "cvs_count",
            "deposit_amount",
        ]


class InfluencerSyncRunSerializer(serializers.ModelSerializer):
    slot_display = serializers.CharField(source="get_slot_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = models.InfluencerSyncRun
        fields = [
            "uuid",
            "slot",
            "slot_display",
            "status",
            "status_display",
            "attempt",
            "row_count",
            "error",
            "created",
        ]


def member_usernames_by_phone(phone_numbers):
    """Synced rows only carry a phone number; map it to our member's username."""
    return dict(
        Member.objects.filter(archived=None, phone_number__in=list(phone_numbers))
        .values_list("phone_number", "user__username")
    )


class InfluencerSyncRunDetailSerializer(InfluencerSyncRunSerializer):
    rows = serializers.SerializerMethodField()

    def get_rows(self, obj):
        rows = [dict(row) for row in InfluencerSnapshotSerializer(obj.rows.all(), many=True).data]
        usernames = member_usernames_by_phone(row["phone_number"] for row in rows)
        for row in rows:
            row["username"] = usernames.get(row["phone_number"])
        return rows

    class Meta(InfluencerSyncRunSerializer.Meta):
        fields = InfluencerSyncRunSerializer.Meta.fields + ["not_found", "rows"]
