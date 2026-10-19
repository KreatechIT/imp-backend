from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from django.utils import timezone

from apps.crmadmin import models as admin_models
from apps.earnings import helper_functions as earnings
from apps.jobs import models
from apps.members.models import Member
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel

TODAY = date(2026, 10, 15)


# Daily job, RM300 a month, RM30 off per missed day. The member joined on the
# 12th, so the 12th, 13th and 14th are closed and the 15th is still open.
class ReviewFlowEndToEndTest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        admin_models.Admin.objects.create(user=self.user, full_name="Base Admin")
        self.admin_user = self.user

        member_user = UserModel.objects.create(username="member_one")
        self.member_user = member_user
        self.member = Member.objects.create(user=member_user, full_name="Member One")

        company = models.Company.objects.create(name="EP369")
        self.job = models.Job.objects.create(
            company=company, title="Posting Story", status=2,
            payment_amount=300, deduction_per_miss=30,
            start_date=timezone.make_aware(datetime(2026, 10, 1)),
        )
        self.requirement = models.JobRequirement.objects.create(
            job=self.job, platform=1, content_type=1, quantity=1,
        )
        self.member_job = models.MemberJob.objects.create(
            member=self.member, job=self.job, status=2, joined=date(2026, 10, 12),
        )

        patcher = mock.patch("django.utils.timezone.localdate", return_value=TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)

    def task_for(self, day):
        key = date(2026, 10, day).isoformat()
        return models.MemberTask.objects.get_or_create(
            member_job=self.member_job, requirement=self.requirement,
            period_key=key,
            defaults={"period_start": date(2026, 10, day), "period_end": date(2026, 10, day)},
        )[0]

    def totals(self):
        data = earnings.earnings_breakdown(self.member.uuid)
        return data["missed_count"], data["deduction"], data["total"]

    def member_submit(self, task, **body):
        self.authenticate(self.member_user)
        return self.client.post(
            f"/members/{self.member.uuid}/tasks/{task.uuid}/submit/",
            data=body, format="json",
        )

    def admin_call(self, method, url, **body):
        self.authenticate(self.admin_user)
        return getattr(self.client, method)(url, data=body, format="json")

    def test_full_flow(self):
        base = f"/jobs/job/{self.job.uuid}/submission"

        # nothing submitted: three closed days are all misses
        assert self.totals() == (3, Decimal("90.00"), Decimal("210.00"))

        # admin switches proof off and widens the window (test dates are in the past)
        self.switch_review_off()
        assert self.admin_call("get", "/jobs/settings/").json()["requires_review"] is False

        # day 12: submitted without proof -> approved straight away, no longer a miss
        day12 = self.task_for(12)
        assert self.member_submit(day12).status_code == 200
        assert self.totals() == (2, Decimal("60.00"), Decimal("240.00"))

        # day 13: submitted, then an admin spot-check finds it fake and rejects it
        day13 = self.task_for(13)
        assert self.member_submit(day13).status_code == 200
        assert self.totals() == (1, Decimal("30.00"), Decimal("270.00"))

        response = self.admin_call(
            "patch", f"{base}/{day13.uuid}/reject/", reject_reason="not posted",
        )
        assert response.status_code == 200, response.json()
        assert self.totals() == (2, Decimal("60.00"), Decimal("240.00"))

        # admin can fix day 13 (rejected) and day 14 (no row at all)
        for period_key in ("2026-10-13", "2026-10-14"):
            response = self.admin_call(
                "post", f"{base}/mark-submitted/",
                member_job_uuid=str(self.member_job.uuid), period_key=period_key,
            )
            assert response.status_code == 200
        assert self.totals() == (0, Decimal("0.00"), Decimal("300.00"))

    def switch_review_off(self):
        response = self.admin_call(
            "patch", "/jobs/settings/",
            requires_review=False, submission_grace_hours=100000,
        )
        assert response.status_code == 200

    def reject_url(self, task):
        return f"/jobs/job/{self.job.uuid}/submission/{task.uuid}/reject/"

    def test_member_cannot_change_the_setting(self):
        self.authenticate(self.member_user)
        response = self.client.patch(
            "/jobs/settings/", data={"requires_review": False}, format="json",
        )
        assert response.status_code == 403
        assert not models.JobSettings.objects.filter(requires_review=False).exists()

    def test_only_auto_approved_tasks_can_be_rejected_after_review(self):
        self.switch_review_off()
        auto = self.task_for(12)
        assert self.member_submit(auto).status_code == 200

        first = self.admin_call("patch", self.reject_url(auto), reject_reason="fake")
        assert first.status_code == 200
        auto.refresh_from_db()
        assert auto.is_approved is False
        assert auto.reviewed_by is not None
        assert not auto.is_auto_approved

        # once an admin has decided, it is final
        again = self.admin_call("patch", self.reject_url(auto), reject_reason="again")
        assert again.status_code == 400

        # a day an admin approved by hand cannot be rejected either
        response = self.admin_call(
            "post", f"/jobs/job/{self.job.uuid}/submission/mark-submitted/",
            member_job_uuid=str(self.member_job.uuid), period_key="2026-10-13",
        )
        assert response.status_code == 200
        manual = models.MemberTask.objects.get(period_key="2026-10-13")
        assert not manual.is_auto_approved
        response = self.admin_call("patch", self.reject_url(manual), reject_reason="x")
        assert response.status_code == 400

    def test_reject_still_requires_a_reason(self):
        self.switch_review_off()
        task = self.task_for(12)
        self.member_submit(task)
        response = self.admin_call("patch", self.reject_url(task))
        assert response.status_code == 400
        task.refresh_from_db()
        assert task.is_auto_approved

    def test_admin_list_flags_auto_approved_submissions(self):
        self.switch_review_off()
        auto = self.task_for(12)
        self.member_submit(auto)
        self.admin_call(
            "post", f"/jobs/job/{self.job.uuid}/submission/mark-submitted/",
            member_job_uuid=str(self.member_job.uuid), period_key="2026-10-13",
        )

        rows = self.admin_call(
            "get", f"/jobs/job/{self.job.uuid}/submission/approved/",
        ).json()["results"]
        flags = {row["period_key"]: row["is_auto_approved"] for row in rows}
        assert flags == {"2026-10-12": True, "2026-10-13": False}

    def test_turning_review_back_on_requires_proof_again(self):
        self.switch_review_off()
        response = self.admin_call("patch", "/jobs/settings/", requires_review=True)
        assert response.status_code == 200

        task = self.task_for(12)
        assert self.member_submit(task).status_code == 400

        response = self.member_submit(task, proof_link="https://instagram.com/p/1")
        assert response.status_code == 200
        task.refresh_from_db()
        assert task.is_approved is None
        assert self.totals()[0] == 3
