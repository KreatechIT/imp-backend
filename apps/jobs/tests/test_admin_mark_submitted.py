from datetime import date, datetime
from unittest import mock

from django.utils import timezone

from apps.crmadmin import models as admin_models
from apps.earnings import helper_functions as earnings
from apps.jobs import models
from apps.members.models import Member
from apps.notifications.models import Notification
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel

TODAY = date(2026, 10, 15)


class AdminMarkSubmittedAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = admin_models.Admin.objects.create(
            user=self.user, full_name="Base Admin",
        )

        member_user = UserModel.objects.create(username="member_one")
        self.member = Member.objects.create(user=member_user, full_name="Member One")

        company = models.Company.objects.create(name="EP369")
        self.job = models.Job.objects.create(
            company=company,
            title="Posting Story 2 Hari",
            status=2,
            deduction_per_miss=30,
            start_date=timezone.make_aware(datetime(2026, 10, 1)),
        )
        self.requirement = models.JobRequirement.objects.create(
            job=self.job, platform=1, content_type=1, quantity=1,
        )
        self.member_job = models.MemberJob.objects.create(
            member=self.member, job=self.job, status=2, joined=date(2026, 10, 1),
        )

        self.base = f"/jobs/job/{self.job.uuid}/submission"
        self.authenticate(self.user)

        patcher = mock.patch("django.utils.timezone.localdate", return_value=TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)

    def missed_keys(self):
        response = self.client.get(f"{self.base}/missed/")
        assert response.status_code == 200
        return [row["period_key"] for row in response.json()]

    def mark(self, period_key, **extra):
        return self.client.post(
            f"{self.base}/mark-submitted/",
            data={
                "member_job_uuid": str(self.member_job.uuid),
                "period_key": period_key,
                **extra,
            },
            format="json",
        )

    def test_lists_exactly_the_closed_days_of_the_month_newest_first(self):
        expected = [f"2026-10-{day:02d}" for day in range(14, 0, -1)]
        assert self.missed_keys() == expected  # the 15th is today, still open

    def test_missed_rows_identify_the_member_and_the_job(self):
        row = self.client.get(f"{self.base}/missed/").json()[0]
        assert row["member"] == "Member One"
        assert row["username"] == "member_one"
        assert row["org"] == "EP369"
        assert row["job_title"] == "Posting Story 2 Hari"
        assert row["requirements"] == [{"platform": 1, "content_type": 1, "quantity": 1}]
        assert row["deduction"] == "30.00"

    def test_mark_submitted_with_no_task_row_removes_the_miss(self):
        assert not models.MemberTask.objects.exists()

        response = self.mark("2026-10-10", note="Posted, confirmed on WhatsApp")
        assert response.status_code == 200

        task = models.MemberTask.objects.get(period_key="2026-10-10")
        assert task.is_approved is True
        assert task.submitted_at is not None
        assert task.reviewed_by == self.admin
        assert task.note == "Posted, confirmed on WhatsApp"
        assert "2026-10-10" not in self.missed_keys()

    def test_mark_submitted_reduces_the_deduction(self):
        before = earnings.missed_breakdown(self.member.uuid)
        self.mark("2026-10-10")
        after = earnings.missed_breakdown(self.member.uuid)

        assert after["missed_count"] == before["missed_count"] - 1
        assert before["deduction"] - after["deduction"] == 30

    def test_rejected_task_can_be_overridden(self):
        models.MemberTask.objects.create(
            member_job=self.member_job, requirement=self.requirement,
            period_key="2026-10-10",
            period_start=date(2026, 10, 10), period_end=date(2026, 10, 10),
            submitted_at=timezone.now(), reviewed_at=timezone.now(),
            is_approved=False, reject_reason="blurry",
        )
        assert "2026-10-10" in self.missed_keys()

        assert self.mark("2026-10-10").status_code == 200
        task = models.MemberTask.objects.get(period_key="2026-10-10")
        assert task.is_approved is True
        assert task.reject_reason is None

    def test_influencer_note_is_kept_when_admin_overrides(self):
        models.MemberTask.objects.create(
            member_job=self.member_job, requirement=self.requirement,
            period_key="2026-10-10",
            period_start=date(2026, 10, 10), period_end=date(2026, 10, 10),
            submitted_at=timezone.now(), reviewed_at=timezone.now(),
            is_approved=False, reject_reason="blurry", note="my story link is in bio",
        )
        self.mark("2026-10-10", note="confirmed on WhatsApp")
        task = models.MemberTask.objects.get(period_key="2026-10-10")
        assert task.note == "my story link is in bio\n[Admin] confirmed on WhatsApp"

    def test_missed_rows_are_newest_day_first_then_by_name(self):
        other_user = UserModel.objects.create(username="aaa")
        other = Member.objects.create(user=other_user, full_name="Aaa Member")
        models.MemberJob.objects.create(
            member=other, job=self.job, status=2, joined=date(2026, 10, 1),
        )
        rows = self.client.get(f"{self.base}/missed/").json()
        assert [r["period_key"] for r in rows[:2]] == ["2026-10-14", "2026-10-14"]
        assert [r["member"] for r in rows[:2]] == ["Aaa Member", "Member One"]

    def test_past_month_is_not_allowed(self):
        response = self.mark("2026-09-30")
        assert response.status_code == 400
        assert not models.MemberTask.objects.exists()

    def test_period_that_is_not_missed_is_not_allowed(self):
        assert self.mark("2026-10-10").status_code == 200
        assert self.mark("2026-10-10").status_code == 400

    def test_member_job_from_another_job_is_refused(self):
        other_job = models.Job.objects.create(
            company=self.job.company, title="Other", status=2,
            start_date=timezone.make_aware(datetime(2026, 10, 1)),
        )
        models.JobRequirement.objects.create(
            job=other_job, platform=1, content_type=1, quantity=1,
        )
        other_member_job = models.MemberJob.objects.create(
            member=self.member, job=other_job, status=2, joined=date(2026, 10, 1),
        )
        response = self.client.post(
            f"{self.base}/mark-submitted/",
            data={
                "member_job_uuid": str(other_member_job.uuid),
                "period_key": "2026-10-10",
            },
            format="json",
        )
        assert response.status_code == 400
        assert not models.MemberTask.objects.filter(member_job=other_member_job).exists()

    def test_missing_fields_are_rejected(self):
        response = self.client.post(f"{self.base}/mark-submitted/", data={}, format="json")
        assert response.status_code == 400

    def test_influencer_is_notified(self):
        self.mark("2026-10-10")
        assert Notification.objects.filter(
            recipient=self.member.user, notification_type=4,
        ).count() == 1

    def test_every_requirement_of_the_day_is_approved(self):
        second = models.JobRequirement.objects.create(
            job=self.job, platform=2, content_type=2, quantity=1,
        )
        assert self.mark("2026-10-10").status_code == 200

        tasks = models.MemberTask.objects.filter(period_key="2026-10-10")
        assert {task.requirement_id for task in tasks} == {self.requirement.id, second.id}
        assert all(task.is_approved for task in tasks)
        assert "2026-10-10" not in self.missed_keys()

    def test_day_with_one_requirement_already_approved_only_fills_the_other(self):
        second = models.JobRequirement.objects.create(
            job=self.job, platform=2, content_type=2, quantity=1,
        )
        approved_at = timezone.now()
        done = models.MemberTask.objects.create(
            member_job=self.member_job, requirement=self.requirement,
            period_key="2026-10-10",
            period_start=date(2026, 10, 10), period_end=date(2026, 10, 10),
            submitted_at=approved_at, reviewed_at=approved_at,
            is_approved=True, note="original",
        )
        assert "2026-10-10" in self.missed_keys()  # still missing the second requirement

        assert self.mark("2026-10-10").status_code == 200

        done.refresh_from_db()
        assert done.note == "original"
        assert done.reviewed_by is None
        assert models.MemberTask.objects.get(
            period_key="2026-10-10", requirement=second,
        ).is_approved is True
        assert "2026-10-10" not in self.missed_keys()

    def test_today_cannot_be_marked(self):
        assert self.mark("2026-10-15").status_code == 400

    def test_member_cannot_list_or_mark(self):
        self.authenticate(self.member.user)
        assert self.client.get(f"{self.base}/missed/").status_code == 403
        assert self.mark("2026-10-10").status_code == 403
        assert not models.MemberTask.objects.exists()

    def test_anonymous_cannot_list_or_mark(self):
        self.client.credentials()
        assert self.client.get(f"{self.base}/missed/").status_code == 401
        assert self.mark("2026-10-10").status_code == 401
