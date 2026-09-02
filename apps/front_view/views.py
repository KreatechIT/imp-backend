from rest_framework.generics import GenericAPIView

from apps.front_view import models, serializers_get
from base import responses
from core import permissions


class TermsPublicView(GenericAPIView):
    """One category's terms, by category in the URL. Never 404s; a
    category with no row yet just returns empty content."""

    serializer_class = serializers_get.SingleTermsAndConditionsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, category, *args, **kwargs):
        terms = models.TermsAndConditions.objects.filter(category=category).first()
        if terms is None:
            return responses.SuccessResponse(data={"content": ""}).get_response()

        data = self.serializer_class(terms).data
        return responses.SuccessResponse(data=data).get_response()
