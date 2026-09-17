from rest_framework import serializers

from . import choices


class StartConnectionSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=choices.PROVIDER_CHOICES, required=True)
