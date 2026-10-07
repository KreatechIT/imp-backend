from decimal import Decimal

import requests
from django.conf import settings
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView

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


LEADERBOARD_SIZE = 20


def fetch_real_leaderboard():
    url = (
        f"{settings.INFLUENCER_API_BASE_URL}"
        f"/third-party/influencer-leaderboard/{settings.INFLUENCER_API_ACCESS_CODE}/"
    )
    try:
        upstream = requests.get(url, timeout=10)
    except requests.RequestException:
        return None

    if upstream.status_code != 200:
        return None

    return upstream.json()


class InfluencerLeaderboardView(APIView):
    """The real ranking from the third-party platform.

    The upstream endpoint is gated only by an access_code in the URL; this
    view keeps that code server-side.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        rows = fetch_real_leaderboard()
        if rows is None:
            return responses.ThirdPartyError().get_response()

        return responses.SuccessResponse(data=rows).get_response()


class LeaderboardView(APIView):
    """The public leaderboard: real ranking plus the admin's dummy
    influencers, best deposit first, top LEADERBOARD_SIZE re-ranked from 1.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        real_rows = fetch_real_leaderboard()
        if real_rows is None:
            return responses.ThirdPartyError().get_response()

        dummy_rows = [
            {
                "member_uuid": str(dummy.uuid),
                "full_name": dummy.full_name,
                "phone_number": dummy.phone_number,
                "reg_count": dummy.reg_count,
                "cvs_count": dummy.cvs_count,
                "deposit_amount": f"{dummy.deposit_amount:.2f}",
            }
            for dummy in models.DummyInfluencer.objects.filter(archived=None)
        ]

        merged = sorted(
            real_rows + dummy_rows,
            key=lambda row: Decimal(str(row["deposit_amount"])),
            reverse=True,
        )[:LEADERBOARD_SIZE]
        data = [{**row, "rank": rank} for rank, row in enumerate(merged, start=1)]

        return responses.SuccessResponse(data=data).get_response()


class InfluencerRankView(APIView):
    """Proxies the third-party influencer rank lookup for one member."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, phone_number=None, *args, **kwargs):
        url = (
            f"{settings.INFLUENCER_API_BASE_URL}"
            f"/third-party/influencer-rank/{phone_number}/{settings.INFLUENCER_API_ACCESS_CODE}/"
        )
        try:
            upstream = requests.get(url, timeout=10)
        except requests.RequestException:
            return responses.ThirdPartyError().get_response()

        if upstream.status_code == 404:
            return responses.MissingItemError(
                item_key="Member", item_id=phone_number,
            ).get_response()

        if upstream.status_code != 200:
            return responses.ThirdPartyError().get_response()

        return responses.SuccessResponse(data=upstream.json()).get_response()
