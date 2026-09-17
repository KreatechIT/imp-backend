import datetime

from django.core import signing
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework.views import APIView

from apps.members.models import Member

from . import models
from .constants import (
    PROVIDER_SCOPES,
    STATE_MAX_AGE_SECONDS,
    STATE_SALT,
    build_result_redirect,
    callback_redirect_uri,
)
from .providers.meta import (
    MetaAPIError,
    exchange_code_for_token,
    exchange_for_long_lived_token,
    get_me,
)


class ThirdPartyOAuthCallbackView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        if request.GET.get("error"):
            return redirect(build_result_redirect("denied"))

        code = request.GET.get("code")
        state = request.GET.get("state")
        if not code or not state:
            return redirect(build_result_redirect("error"))

        try:
            payload = signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE_SECONDS)
        except signing.BadSignature:
            return redirect(build_result_redirect("error"))

        try:
            member = Member.objects.get(uuid=payload["member_uuid"], archived=None)
        except Member.DoesNotExist:
            return redirect(build_result_redirect("error"))

        provider = payload["provider"]

        try:
            short_lived = exchange_code_for_token(code, callback_redirect_uri(request))
            long_lived = exchange_for_long_lived_token(short_lived["access_token"])
            me = get_me(long_lived["access_token"])
        except MetaAPIError:
            return redirect(build_result_redirect("error"))

        expires_in = long_lived.get("expires_in")
        expires_at = (
            timezone.now() + datetime.timedelta(seconds=int(expires_in))
            if expires_in else None
        )

        connection, _created = models.ThirdPartyConnection.objects.update_or_create(
            member=member, provider=provider, archived=None,
            defaults={
                "account_id": me.get("id", ""),
                "account_label": me.get("name", ""),
                "token_expires_at": expires_at,
                "scopes": ",".join(PROVIDER_SCOPES[provider]),
            },
        )
        connection.set_access_token(long_lived["access_token"])
        connection.save()

        return redirect(build_result_redirect("success"))
