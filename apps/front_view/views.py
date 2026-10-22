from datetime import date
from decimal import Decimal

import requests

from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView

from apps.front_view import influencer_sync, models, serializers_get
from apps.members.models import Member
from base import responses
from core import permissions


class TermsPublicView(GenericAPIView):
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


def stored_rows(include_username=False):
    run = influencer_sync.latest_run()
    if run is None:
        return []
    rows = [
        dict(row) for row in
        serializers_get.InfluencerSnapshotSerializer(run.rows.all(), many=True).data
    ]
    members = {
        phone: (full_name, username)
        for phone, full_name, username in Member.objects.filter(
            archived=None, phone_number__in=[row["phone_number"] for row in rows],
        ).values_list("phone_number", "full_name", "user__username")
    }
    for row in rows:
        full_name, username = members.get(row["phone_number"], (None, None))
        row["full_name"] = full_name or row["full_name"]
        # Admin view only; the public leaderboard never exposes usernames.
        if include_username:
            row["username"] = username
    return rows


class InfluencerLeaderboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return responses.SuccessResponse(data=stored_rows(include_username=True)).get_response()


def merged_rows():
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
    permission_classes = [permissions.IsAdmin]

    def get(self, request, phone_number=None, *args, **kwargs):
        data = rank_payload(list(stored_rows()), phone_number)
        if data is None:
            return responses.MissingItemError(
                item_key="Member", item_id=phone_number,
            ).get_response()

        return responses.SuccessResponse(data=data).get_response()


class InfluencerReportView(APIView):
    """Admin report from the MRS imp-report API: registers, bonus claims,
    deposits, withdrawals and win/lose per influencer for a date range
    (?from_date=&to_date=, YYYY-MM-DD, default the current month)."""

    permission_classes = [permissions.IsAdmin]

    def get(self, request, *args, **kwargs):
        from_date = request.query_params.get("from_date") or None
        to_date = request.query_params.get("to_date") or None
        try:
            start = date.fromisoformat(from_date) if from_date else None
            end = date.fromisoformat(to_date) if to_date else None
        except ValueError:
            return responses.BadRequestError(
                details="Use YYYY-MM-DD for from_date and to_date",
            ).get_response()
        if start and end and start > end:
            return responses.BadRequestError(
                details="from_date must not be after to_date",
            ).get_response()

        phones = influencer_sync.influencer_phones()
        if not phones:
            return responses.SuccessResponse(
                data={"results": [], "not_found": []},
            ).get_response()

        try:
            payload = influencer_sync.fetch_report(phones, from_date, to_date)
        except (requests.RequestException, ValueError):
            return responses.ThirdPartyError(
                error_message="Unable to load the report from MRS",
            ).get_response()

        members = {
            m.phone_number: m
            for m in Member.objects.filter(
                archived=None, phone_number__in=phones,
            ).select_related("user")
        }
        results = []
        for row in payload.get("results", []):
            member = members.get(row.get("phone_number"))
            results.append({
                **row,
                "username": member.user.username if member else "",
                "full_name": (member.full_name if member else "") or "",
            })
        results.sort(key=lambda r: Decimal(str(r.get("total_deposit") or "0")), reverse=True)

        return responses.SuccessResponse(
            data={"results": results, "not_found": payload.get("not_found", [])},
        ).get_response()
