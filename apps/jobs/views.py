from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.serializers import ValidationError

from apps.jobs import models, serializers_create, serializers_get
from base import responses
from core import permissions


class JobSettingsView(GenericAPIView):
    permission_classes = [permissions.IsAdmin]
    serializer_class = serializers_get.JobSettingsSerializer

    def get_settings(self):
        settings_row, _ = models.JobSettings.objects.get_or_create(
            singleton_enforcer=True,
        )
        return settings_row

    def get(self, request, *args, **kwargs):
        data = self.serializer_class(self.get_settings()).data
        return responses.SuccessResponse(data=data).get_response()

    @extend_schema(request=serializers_create.JobSettingsSerializer)
    def patch(self, request, *args, **kwargs):
        serializer = serializers_create.JobSettingsSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()

        settings_row = self.get_settings()
        settings_row.update(**serializer.validated_data)

        data = self.serializer_class(settings_row).data
        return responses.SuccessResponse(data=data).get_response()
