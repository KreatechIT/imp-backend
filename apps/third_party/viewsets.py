from django.core import signing
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from base import responses

from . import models, serializers_create, serializers_get
from .constants import PROVIDER_SCOPES, STATE_SALT, callback_redirect_uri
from .permissions import IsKocMember
from .providers.meta import build_authorize_url


class SocialMediaConnectionViewSet(ReadOnlyModelViewSet):
    serializer_class = serializers_get.ThirdPartyConnectionSerializer
    permission_classes = [IsKocMember]
    lookup_field = "uuid"
    item_key = "Connection Id"

    def get_member(self):
        return self.request.user.member

    def get_queryset(self):
        member_uuid = self.kwargs.get("member_uuid")
        return (
            models.ThirdPartyConnection.objects
            .filter(member=self.get_member(), member__uuid=member_uuid, archived=None)
            .order_by("provider")
        )

    @extend_schema(request=serializers_create.StartConnectionSerializer)
    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request, member_uuid=None, *args, **kwargs):
        serializer = serializers_create.StartConnectionSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return responses.InvalidDataError(details=e.detail).get_response()
        provider = serializer.validated_data["provider"]

        state = signing.dumps(
            {"member_uuid": str(self.get_member().uuid), "provider": provider},
            salt=STATE_SALT,
        )
        authorize_url = build_authorize_url(
            redirect_uri=callback_redirect_uri(request),
            state=state,
            scopes=PROVIDER_SCOPES[provider],
        )
        return responses.SuccessResponse(data={"authorize_url": authorize_url}).get_response()

    @action(detail=True, methods=["patch"])
    def disconnect(self, request, uuid=None, member_uuid=None, *args, **kwargs):
        try:
            connection = self.get_queryset().get(uuid=uuid)
        except models.ThirdPartyConnection.DoesNotExist:
            return responses.MissingItemError(item_key=self.item_key, item_id=uuid).get_response()

        connection.archive()
        data = self.serializer_class(connection, context={"request": self.request}).data
        return responses.SuccessResponse(data=data).get_response()
