import requests
from django.conf import settings
from django.db import transaction

from apps.front_view import choices, models
from apps.members.models import Member


def influencer_phones():
    """Every live member's phone, exactly as stored (MRS matches exactly)."""
    phones = (
        Member.objects.filter(archived=None)
        .exclude(phone_number__isnull=True)
        .exclude(phone_number="")
        .values_list("phone_number", flat=True)
    )
    return list(phones)


def fetch_from_third_party(phones):
    response = requests.post(
        f"{settings.INFLUENCER_API_BASE_URL}/third-party/influencer-leaderboard/",
        json={
            "access_code": settings.INFLUENCER_API_ACCESS_CODE,
            "phone_numbers": phones,
        },
        timeout=choices.INFLUENCER_SYNC_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def run_sync(slot, attempt):
    """Pull the ranking and store it as a new run. Earlier runs are kept.
    Returns the number of rows stored."""
    phones = influencer_phones()
    if not phones:
        return 0

    payload = fetch_from_third_party(phones)
    results = payload["results"]

    with transaction.atomic():
        run = models.InfluencerSyncRun.objects.create(
            slot=slot,
            status=1,
            attempt=attempt,
            row_count=len(results),
            not_found=payload.get("not_found", []),
        )
        models.InfluencerSnapshot.objects.bulk_create([
            models.InfluencerSnapshot(
                run=run,
                rank=row["rank"],
                member_uuid=row["member_uuid"],
                full_name=row.get("full_name") or "",
                phone_number=row.get("phone_number") or "",
                reg_count=row["reg_count"],
                cvs_count=row["cvs_count"],
                deposit_amount=row["deposit_amount"],
            )
            for row in results
        ])
    return len(results)


def record_failure(slot, attempt, exc):
    models.InfluencerSyncRun.objects.create(
        slot=slot,
        status=2,
        attempt=attempt,
        error=f"{type(exc).__name__}: {exc}"[:2000],
    )


def latest_run():
    """The newest successful run, or None before the first sync."""
    return (
        models.InfluencerSyncRun.objects
        .filter(status=1)
        .order_by("-created")
        .first()
    )
