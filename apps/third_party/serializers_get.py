from rest_framework import serializers

from . import models


class ThirdPartyConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ThirdPartyConnection
        fields = [
            "uuid",
            "provider",
            "account_label",
            "connected_at",
            "is_expired",
        ]
