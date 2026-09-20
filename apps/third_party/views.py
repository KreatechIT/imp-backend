from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone
from rest_framework.views import APIView

from apps.notifications import helper_functions as notifications
from base import responses
from core import permissions

from . import facebook, instagram, models

STATE_SALT = "third-party-oauth-state"
STATE_MAX_AGE = 600

PROVIDERS = {
    1: instagram,
    2: facebook,
}


def _redirect_uri():
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{base}{settings.THIRD_PARTY_CALLBACK_PATH}"


def _member_of(request, member_uuid):
    member = getattr(request.user, "member", None)
    if member is None or str(member.uuid) != str(member_uuid):
        return None
    return member


class SocialMediaConnectionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, member_uuid=None, *args, **kwargs):
        member = _member_of(request, member_uuid)
        if member is None:
            return responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        results = [
            {
                "uuid": str(connection.uuid),
                "provider": connection.provider,
                "account_id": connection.account_id,
                "account_label": connection.account_label,
                "connected_at": connection.connected_at,
                "is_expired": connection.is_expired,
            }
            for connection in models.ThirdPartyConnection.objects.filter(
                member=member, archived=None,
            ).order_by("provider")
        ]
        return responses.SuccessResponse(data={"results": results}).get_response()


class SocialMediaStartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, member_uuid=None, *args, **kwargs):
        member = _member_of(request, member_uuid)
        if member is None:
            return responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        try:
            provider = int(request.data.get("provider"))
        except (TypeError, ValueError):
            provider = None
        if provider not in PROVIDERS:
            return responses.InvalidDataError(
                details={"provider": ["Choose Instagram (1) or Facebook (2)."]},
            ).get_response()

        state = signing.dumps(
            {"member_uuid": str(member.uuid), "provider": provider}, salt=STATE_SALT,
        )
        return responses.SuccessResponse(data={
            "authorize_url": PROVIDERS[provider].authorize_url(_redirect_uri(), state),
            "provider": provider,
        }).get_response()


class SocialMediaExchangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, member_uuid=None, *args, **kwargs):
        member = _member_of(request, member_uuid)
        if member is None:
            return responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        code, state = request.data.get("code"), request.data.get("state")
        if not code or not state:
            return self._failed("That connection didn't complete. Please try again.")

        try:
            payload = signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE)
        except signing.BadSignature:
            return self._failed("This connection link has expired. Please try again.")

        if payload.get("member_uuid") != str(member.uuid):
            return self._failed("This connection belongs to a different account.")

        provider = payload["provider"]
        module = PROVIDERS[provider]

        try:
            accounts = module.connect(code, _redirect_uri())
        except (facebook.FacebookError, instagram.InstagramError) as e:
            return self._failed(str(e), provider)

        if not accounts:
            return self._failed("No account was returned to connect.", provider)

        connected = []
        for account_id, account_label, token, expires_in in accounts:
            connection, _ = models.ThirdPartyConnection.objects.update_or_create(
                member=member, provider=provider, account_id=account_id, archived=None,
                defaults={
                    "account_label": account_label,
                    "scopes": ",".join(module.SCOPES),
                    "token_expires_at": (
                        timezone.now() + timedelta(seconds=int(expires_in))
                        if expires_in else None
                    ),
                },
            )
            connection.set_access_token(token)
            connection.save()
            connected.append({
                "uuid": str(connection.uuid),
                "account_id": connection.account_id,
                "account_label": connection.account_label,
            })

        notifications.notify(
            recipient=member.user,
            role=2,
            notification_type=16,
            title="Account connected",
            message=", ".join(a["account_label"] for a in connected if a["account_label"]),
        )

        return responses.SuccessResponse(data={
            "status": "connected",
            "provider": provider,
            "accounts": connected,
            "uuid": connected[0]["uuid"],
            "account_label": (
                connected[0]["account_label"] if len(connected) == 1
                else f"{len(connected)} accounts"
            ),
        }).get_response()

    @staticmethod
    def _failed(message, provider=None):
        return responses.SuccessResponse(data={
            "status": "failed",
            "provider": provider,
            "message": message,
        }).get_response()


class SocialMediaDisconnectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, member_uuid=None, uuid=None, *args, **kwargs):
        member = _member_of(request, member_uuid)
        if member is None:
            return responses.MissingItemError(
                item_key="Member Id", item_id=member_uuid,
            ).get_response()

        connection = models.ThirdPartyConnection.objects.filter(
            uuid=uuid, member=member, archived=None,
        ).first()
        if connection is None:
            return responses.MissingItemError(
                item_key="Connection Id", item_id=uuid,
            ).get_response()

        connection.archive()
        return responses.SuccessResponse(data={
            "uuid": str(connection.uuid),
            "provider": connection.provider,
        }).get_response()
