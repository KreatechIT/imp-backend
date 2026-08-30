import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.jobs import models as job_models
from apps.jobs.helper_functions import resolve_period
from apps.members.models import Member


def _month_end(day):
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def month_bounds(month_key=None):
    today = timezone.localdate()
    if month_key:
        year, month = (int(part) for part in month_key.split("-"))
    else:
        year, month = today.year, today.month
    return (
        f"{year}-{month:02d}",
        date(year, month, 1),
        date(year, month, calendar.monthrange(year, month)[1]),
    )


def _job_window(job, from_date, to_date):
    start = max(from_date, timezone.localtime(job.start_date).date())
    end = to_date
    if job.end_date:
        end = min(end, timezone.localtime(job.end_date).date())
    return start, end


def iter_periods(job, from_date, to_date):
    day, limit = _job_window(job, from_date, to_date)
    while day <= limit:
        period_key, period_start, period_end = resolve_period(job, day)
        yield period_key, period_start, period_end
        day = period_end + timedelta(days=1)


def _cycle_end(day, payment_period):
    if payment_period == 1:
        return day
    if payment_period == 2:
        _, _, weekday = day.isocalendar()
        return day + timedelta(days=7 - weekday)
    return _month_end(day)


def payment_cycles(job, from_date, to_date):
    day, limit = _job_window(job, from_date, to_date)
    cycles = 0
    while day <= limit:
        cycles += 1
        day = min(_cycle_end(day, job.payment_period), limit) + timedelta(days=1)
    return cycles


def _member_jobs(from_date, to_date, member_uuids=None):
    queryset = (
        job_models.MemberJob.objects
        .filter(
            archived=None,
            status__in=[2, 3],
            member__archived=None,
            job__archived=None,
            job__start_date__date__lte=to_date,
        )
        .filter(
            Q(job__end_date__isnull=True) | Q(job__end_date__date__gte=from_date)
        )
        .select_related("job__company", "member")
        .prefetch_related(
            Prefetch(
                "job__requirements",
                queryset=job_models.JobRequirement.objects.filter(archived=None),
            )
        )
    )
    if member_uuids is not None:
        queryset = queryset.filter(member__uuid__in=member_uuids)
    return queryset


def member_jobs_in_range(member_uuid, from_date, to_date):
    return _member_jobs(from_date, to_date, [member_uuid])


def _approved_requirements(member_jobs, from_date, to_date):
    rows = (
        job_models.MemberTask.objects
        .filter(
            member_job__in=member_jobs,
            is_approved=True,
            period_start__lte=to_date,
            period_end__gte=from_date,
        )
        .values_list("member_job_id", "period_key", "requirement_id")
    )

    approved = {}
    for member_job_id, period_key, requirement_id in rows:
        periods = approved.setdefault(member_job_id, {})
        periods.setdefault(period_key, set()).add(requirement_id)
    return approved


def period_results(member_job, from_date, to_date, approved_periods=None):
    job = member_job.job
    required = len(job.requirements.all())
    if not required:
        return [], 0

    if approved_periods is None:
        approved_periods = _approved_requirements(
            [member_job], from_date, to_date,
        ).get(member_job.id, {})

    today = timezone.localdate()
    missed = []
    posted = 0
    for period_key, period_start, period_end in iter_periods(job, from_date, to_date):
        if period_end >= today:
            continue
        if len(approved_periods.get(period_key, ())) < required:
            missed.append({
                "period_key": period_key,
                "period_start": period_start,
                "period_end": period_end,
            })
        else:
            posted += 1
    return missed, posted


def blank_breakdown(period_key, from_date, to_date):
    return {
        "period_key": period_key,
        "from_date": from_date,
        "to_date": to_date,
        "base_pay": Decimal("0.00"),
        "missed_count": 0,
        "posted_count": 0,
        "deduction": Decimal("0.00"),
        "total": Decimal("0.00"),
        "jobs": [],
    }


def earnings_breakdowns(member_uuids=None, month_key=None):
    period_key, from_date, to_date = month_bounds(month_key)
    member_jobs = list(_member_jobs(from_date, to_date, member_uuids))
    approved = _approved_requirements(member_jobs, from_date, to_date)

    breakdowns = {}
    for member_job in member_jobs:
        job = member_job.job
        cycles = payment_cycles(job, from_date, to_date)
        missed, posted = period_results(
            member_job, from_date, to_date, approved.get(member_job.id, {}),
        )

        base = job.payment_amount * cycles
        deduction_per_miss = job.deduction_per_miss or Decimal("0.00")
        deduction = deduction_per_miss * len(missed)

        breakdown = breakdowns.setdefault(
            member_job.member.uuid,
            blank_breakdown(period_key, from_date, to_date),
        )
        breakdown["base_pay"] += base
        breakdown["deduction"] += deduction
        breakdown["missed_count"] += len(missed)
        breakdown["posted_count"] += posted
        breakdown["total"] = breakdown["base_pay"] - breakdown["deduction"]
        breakdown["jobs"].append({
            "member_job_uuid": member_job.uuid,
            "company": job.company.name,
            "job_title": job.title,
            "payment_amount": job.payment_amount,
            "payment_period": job.get_payment_period_display(),
            "cycles": cycles,
            "base_pay": base,
            "missed_count": len(missed),
            "posted_count": posted,
            "deduction": deduction,
            "total": base - deduction,
            "deduction_per_miss": deduction_per_miss,
            "missed_days": missed,
        })

    return period_key, from_date, to_date, breakdowns


def earnings_breakdown(member_uuid, month_key=None):
    period_key, from_date, to_date, breakdowns = earnings_breakdowns(
        [member_uuid], month_key,
    )
    return breakdowns.get(
        member_uuid, blank_breakdown(period_key, from_date, to_date),
    )


def missed_breakdown(member_uuid, month_key=None):
    breakdown = earnings_breakdown(member_uuid, month_key)

    days = []
    deduction_total = Decimal("0.00")

    for job in breakdown["jobs"]:
        deduction_per_miss = job["deduction_per_miss"]
        for missed in job["missed_days"]:
            deduction_total += deduction_per_miss
            days.append({
                "member_job_uuid": job["member_job_uuid"],
                "company": job["company"],
                "job_title": job["job_title"],
                "period_key": missed["period_key"],
                "period_start": missed["period_start"],
                "period_end": missed["period_end"],
                "deduction": deduction_per_miss,
            })

    days.sort(key=lambda day: day["period_start"], reverse=True)

    return {
        "period_key": breakdown["period_key"],
        "from_date": breakdown["from_date"],
        "to_date": breakdown["to_date"],
        "missed_count": len(days),
        "deduction": deduction_total,
        "days": days,
    }


def member_rows(members, breakdowns, period_key, from_date, to_date):
    rows = []
    for member in members:
        breakdown = breakdowns.get(
            member.uuid, blank_breakdown(period_key, from_date, to_date),
        )
        rows.append({
            "member_uuid": member.uuid,
            "full_name": member.full_name,
            "username": member.user.username,
            "phone_number": member.phone_number,
            "email": member.email,
            "status": member.get_status_display(),
            "job_count": len(breakdown["jobs"]),
            "base_pay": breakdown["base_pay"],
            "missed_count": breakdown["missed_count"],
            "posted_count": breakdown["posted_count"],
            "deduction": breakdown["deduction"],
            "total": breakdown["total"],
        })
    return rows


SORT_FIELDS = {
    "total": ("total", False),
    "-total": ("total", True),
    "missed": ("missed_count", False),
    "-missed": ("missed_count", True),
    "deduction": ("deduction", False),
    "-deduction": ("deduction", True),
    "name": ("full_name", False),
}


def statistics(month_key=None, search=None, status=None, sort=None,
               min_total=None, max_total=None):
    members = (
        Member.objects
        .filter(archived=None)
        .select_related("user")
        .order_by("-created")
    )
    if search:
        members = members.filter(
            Q(full_name__icontains=search)
            | Q(user__username__icontains=search)
            | Q(phone_number__icontains=search)
            | Q(email__icontains=search)
        )
    if status:
        members = members.filter(status=status)

    members = list(members)
    period_key, from_date, to_date, breakdowns = earnings_breakdowns(
        [member.uuid for member in members], month_key,
    )
    rows = member_rows(members, breakdowns, period_key, from_date, to_date)

    if min_total is not None:
        rows = [row for row in rows if row["total"] >= min_total]
    if max_total is not None:
        rows = [row for row in rows if row["total"] <= max_total]

    field, reverse = SORT_FIELDS.get(sort or "-total", ("total", True))
    rows.sort(key=lambda row: row[field] or 0, reverse=reverse)

    summary = {
        "period_key": period_key,
        "from_date": from_date,
        "to_date": to_date,
        "member_count": len(rows),
        "earning_member_count": len([r for r in rows if r["total"] > 0]),
        "missed_member_count": len([r for r in rows if r["missed_count"] > 0]),
        "base_pay": sum((row["base_pay"] for row in rows), Decimal("0.00")),
        "posted_count": sum(row["posted_count"] for row in rows),
        "missed_count": sum(row["missed_count"] for row in rows),
        "deduction": sum((row["deduction"] for row in rows), Decimal("0.00")),
        "total": sum((row["total"] for row in rows), Decimal("0.00")),
    }
    return summary, rows


def earnings_kpi():
    member_count = Member.objects.filter(archived=None).count()
    _, _, _, breakdowns = earnings_breakdowns()

    base_pay = Decimal("0.00")
    deduction = Decimal("0.00")
    total = Decimal("0.00")
    missed_count = 0
    posted_count = 0
    earning_member_count = 0
    missed_member_count = 0

    for breakdown in breakdowns.values():
        base_pay += breakdown["base_pay"]
        deduction += breakdown["deduction"]
        total += breakdown["total"]
        missed_count += breakdown["missed_count"]
        posted_count += breakdown["posted_count"]
        if breakdown["total"] > 0:
            earning_member_count += 1
        if breakdown["missed_count"]:
            missed_member_count += 1

    return {
        "member_count": member_count,
        "earning_member_count": earning_member_count,
        "missed_member_count": missed_member_count,
        "base_pay": base_pay,
        "posted_count": posted_count,
        "missed_count": missed_count,
        "deduction": deduction,
        "total": total,
    }
