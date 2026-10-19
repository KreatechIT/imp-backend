from datetime import timedelta

from django.utils import timezone

from apps.crmadmin import models as admin_models
from apps.jobs import models
from apps.members.models import Member
from apps.notifications.models import Notification
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


class SubmitReviewSettingAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        admin_models.Admin.objects.create(user=self.user, full_name="Base Admin")

        member_user = UserModel.objects.create(username="member_one")
        self.member = Member.objects.create(user=member_user, full_name="Member One")

        company = models.Company.objects.create(name="KGAME99")
        self.job = models.Job.objects.create(
            company=company,
            title="Daily Posting Job",
            status=2,
            start_date=timezone.now() - timedelta(days=10),
        )
        requirement = models.JobRequirement.objects.create(
            job=self.job, platform=1, content_type=2, quantity=1,
        )
        member_job = models.MemberJob.objects.create(
            member=self.member, job=self.job, status=2,
        )

        # keyed on today's date so the "today" endpoint returns this very task
        today = timezone.localdate()
        self.task = models.MemberTask.objects.create(
            member_job=member_job, requirement=requirement,
            period_key=today.isoformat(), period_start=today, period_end=today,
        )
        self.url = f"/members/{self.member.uuid}/tasks/{self.task.uuid}/submit/"
        self.today_url = f"/members/{self.member.uuid}/tasks/today/"
        self.authenticate(self.member.user)

    def set_requires_review(self, value):
        models.JobSettings.objects.update_or_create(
            singleton_enforcer=True, defaults={"requires_review": value},
        )

    def admin_notifications(self):
        return Notification.objects.filter(recipient=self.user, notification_type=3)

    def test_default_requires_proof(self):
        response = self.client.post(self.url, data={}, format="json")
        assert response.status_code == 400
        self.task.refresh_from_db()
        assert self.task.submitted_at is None

    def test_review_on_proof_submission_waits_for_admin(self):
        self.set_requires_review(True)
        response = self.client.post(
            self.url, data={"proof_link": "https://instagram.com/p/1"}, format="json",
        )
        assert response.status_code == 200
        self.task.refresh_from_db()
        assert self.task.submitted_at is not None
        assert self.task.reviewed_at is None
        assert self.task.is_approved is None
        assert self.admin_notifications().count() == 1

    def test_review_off_allows_submission_without_proof_and_auto_approves(self):
        self.set_requires_review(False)
        response = self.client.post(self.url, data={}, format="json")
        assert response.status_code == 200
        self.task.refresh_from_db()
        assert self.task.submitted_at is not None
        assert self.task.is_approved is True
        assert self.task.reviewed_at is not None
        assert self.task.reviewed_by is None
        assert self.task.is_auto_approved
        assert self.task.is_fulfilled
        assert not self.admin_notifications().exists()

    def test_review_off_keeps_proof_when_given(self):
        self.set_requires_review(False)
        response = self.client.post(
            self.url, data={"proof_link": "https://instagram.com/p/1"}, format="json",
        )
        assert response.status_code == 200
        self.task.refresh_from_db()
        assert self.task.proof_link == "https://instagram.com/p/1"
        assert self.task.is_approved is True

    def test_review_off_still_blocks_a_second_submission(self):
        self.set_requires_review(False)
        assert self.client.post(self.url, data={}, format="json").status_code == 200
        assert self.client.post(self.url, data={}, format="json").status_code == 400

    def test_task_reports_whether_proof_is_required(self):
        self.set_requires_review(True)
        row = self.client.get(self.today_url).json()[0]
        assert row["uuid"] == str(self.task.uuid)
        assert row["proof_required"] is True

        self.set_requires_review(False)
        assert self.client.get(self.today_url).json()[0]["proof_required"] is False

    def test_task_carries_the_job_script_and_description(self):
        self.job.script = "Member baru register boleh dapat RM50"
        self.job.description = "Guidelines"
        self.job.save()

        row = self.client.get(self.today_url).json()[0]
        assert row["uuid"] == str(self.task.uuid)
        assert row["job_script"] == "Member baru register boleh dapat RM50"
        assert row["job_description"] == "Guidelines"

    def test_task_with_no_script_or_description_returns_empty_values(self):
        row = self.client.get(self.today_url).json()[0]
        assert not row["job_script"]
        assert not row["job_description"]

    def test_script_is_returned_even_after_the_job_has_ended(self):
        self.job.script = "still visible"
        self.job.end_date = timezone.now() - timedelta(days=1)
        self.job.save()

        response = self.client.get(f"/members/{self.member.uuid}/tasks/{self.task.uuid}/")
        assert response.status_code == 200
        assert response.json()["job_script"] == "still visible"
