from decimal import Decimal

from apps.earnings.helper_functions import earnings_breakdown
from apps.members.models import Member


def ranking_rows():
    rows = []
    for member in Member.objects.filter(archived=None).select_related("user"):
        breakdown = earnings_breakdown(member.uuid)
        rows.append({
            "member_uuid": member.uuid,
            "full_name": member.full_name,
            "username": member.user.username,
            "amount": breakdown["total"],
        })

    rows.sort(key=lambda row: row["amount"], reverse=True)
    for position, row in enumerate(rows, start=1):
        row["ranking"] = position

    return rows


def member_ranking(member_uuid):
    rows = ranking_rows()

    row = next(
        (
            row for row in rows
            if str(row["member_uuid"]) == str(member_uuid)
        ),
        None,
    )
    if row is None:
        return None

    above = rows[row["ranking"] - 2] if row["ranking"] > 1 else None

    return {
        "member_uuid": row["member_uuid"],
        "full_name": row["full_name"],
        "username": row["username"],
        "ranking": row["ranking"],
        "amount": row["amount"],
        "next_rank": above["ranking"] if above else None,
        "next_rank_amount": above["amount"] if above else None,
        "amount_needed": (
            above["amount"] - row["amount"] if above else Decimal("0.00")
        ),
    }


def ranking_kpi():
    rows = ranking_rows()
    amounts = [row["amount"] for row in rows]
    earning = [amount for amount in amounts if amount > 0]

    return {
        "member_count": len(rows),
        "earning_member_count": len(earning),
        "total_amount": sum(amounts, Decimal("0.00")),
        "average_amount": (
            round(sum(earning, Decimal("0.00")) / len(earning), 2)
            if earning else Decimal("0.00")
        ),
        "top_amount": amounts[0] if amounts else Decimal("0.00"),
    }
