import bleach

from functools import partial
from rest_framework import serializers
from rest_framework.fields import SkipField


class CustomImageSerializer(serializers.ImageField):
    """Skips the field when the existing url string is resubmitted unchanged."""

    def to_internal_value(self, data):
        if isinstance(data, str):
            raise SkipField()
        file_object = super().to_internal_value(data)
        django_field = self._DjangoImageField()
        django_field.error_messages = self.error_messages
        return django_field.clean(file_object)


class SanitizedHTMLField(serializers.CharField):
    def __init__(self, *args, **kwargs):
        self.allowed_tags = kwargs.pop('allowed_tags', [
            'p', 'b', 'i', 'u', 'ul', 'ol', 'li', 'br', 'strong', 'em',
            'h1', 'h2', 'h3', 'h4', 'blockquote', 'a', 'span',
        ])
        self.allowed_attributes = kwargs.pop('allowed_attributes', {
            'a': ['href', 'title', 'target', 'rel'],
        })
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        return bleach.clean(
            value, tags=self.allowed_tags, attributes=self.allowed_attributes
        )


NotRequiredCharField = partial(
    serializers.CharField,
    required=False,
    allow_null=True,
    allow_blank=True,
)


class NullableUUIDField(serializers.UUIDField):
    def to_internal_value(self, data):
        if data in [None, '']:
            return None
        return super().to_internal_value(data)
