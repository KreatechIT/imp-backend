from decimal import Decimal

from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView

from apps.front_view import influencer_sync, models, serializers_get
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


def mask_name(name):
    name = (name or "").strip()
    if not name:
        return ""
    if len(name) <= 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def mask_phone(phone):
    phone = (phone or "").strip()
    if len(phone) <= 4:
        return "*" * len(phone)
    return "*" * (len(phone) - 4) + phone[-4:]


def stored_rows():
    """The ranking from the newest successful sync, [] before the first."""
    run = influencer_sync.latest_run()
    if run is None:
        return []
    return serializers_get.InfluencerSnapshotSerializer(
        run.rows.all(), many=True,
    ).data


class InfluencerLeaderboardView(APIView):
    """The real ranking as of the last sync (see influencer_sync). Nothing
    here calls the third party."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return responses.SuccessResponse(data=stored_rows()).get_response()


def merged_rows():
    """Real ranking plus the admin's dummy influencers, best deposit first,
    ranked from 1. Not trimmed and not masked."""
    real_rows = [dict(row) for row in stored_rows()]
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
    )
    return [{**row, "rank": rank} for rank, row in enumerate(merged, start=1)]


class LeaderboardView(APIView):
    """The public leaderboard: the top LEADERBOARD_SIZE of merged_rows.
    Names show only the first and last character, phone numbers only the
    last 4 digits.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        data = [
            {
                **row,
                "full_name": mask_name(row.get("full_name")),
                "phone_number": mask_phone(row.get("phone_number")),
            }
            for row in merged_rows()[:LEADERBOARD_SIZE]
        ]
        return responses.SuccessResponse(data=data).get_response()


def rank_payload(rows, phone_number):
    """The row for one phone with the gap to the rank above, or None."""
    index = next(
        (i for i, row in enumerate(rows) if row["phone_number"] == phone_number),
        None,
    )
    if index is None:
        return None

    above = rows[index - 1] if index > 0 else None
    return {
        **rows[index],
        "next_rank": above["rank"] if above else None,
        "next_rank_amount": above["deposit_amount"] if above else None,
    }


class MyLeaderboardRankView(APIView):
    """The signed-in member's own place on the public board (real plus dummy
    influencers, so it matches what the board shows), with their stats and
    the gap to the rank above. rank is null when they are not in the last
    sync yet. Their own data, so nothing is masked."""

    permission_classes = [permissions.IsMember]

    def get(self, request, *args, **kwargs):
        member = request.user.member
        data = rank_payload(merged_rows(), member.phone_number) or {
            "rank": None,
            "member_uuid": None,
            "full_name": member.full_name,
            "phone_number": member.phone_number,
            "reg_count": 0,
            "cvs_count": 0,
            "deposit_amount": "0.00",
            "next_rank": None,
            "next_rank_amount": None,
        }
        run = influencer_sync.latest_run()
        data["in_top_board"] = bool(data["rank"] and data["rank"] <= LEADERBOARD_SIZE)
        data["synced_at"] = run.created if run else None

        return responses.SuccessResponse(data=data).get_response()


class InfluencerRankView(APIView):
    """Admin lookup of any member's place in the real (last synced) ranking
    by phone, with the gap to the rank above."""

    permission_classes = [permissions.IsAdmin]

    def get(self, request, phone_number=None, *args, **kwargs):
        data = rank_payload(list(stored_rows()), phone_number)
        if data is None:
            return responses.MissingItemError(
                item_key="Member", item_id=phone_number,
            ).get_response()

        return responses.SuccessResponse(data=data).get_response()
