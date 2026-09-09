from datetime import timedelta

from django.utils import timezone

from apps.crmadmin import models as admin_models
from apps.jobs import models
from apps.jobs.tasks import send_pending_result_reminders
from apps.members.models import Member
from apps.notifications.models import Notification
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


class MemberPendingResultsAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()

        member_user = UserModel.objects.create(username="member_one")
        self.member = Member.objects.create(user=member_user, full_name="Member One")

        self.company = models.Company.objects.create(name="KGAME99")
        self.job = models.Job.objects.create(
            company=self.company,
            title="Daily Posting Job",
            start_date=timezone.now() - timedelta(days=10),
        )
        self.requirement = models.JobRequirement.objects.create(
            job=self.job, platform=1, content_type=2, quantity=1,
        )
        self.member_job = models.MemberJob.objects.create(
            member=self.member, job=self.job,
        )

        today = timezone.localdate()
        self.task_done = models.MemberTask.objects.create(
            member_job=self.member_job, requirement=self.requirement,
            period_key="d1", period_start=today - timedelta(days=3),
            period_end=today - timedelta(days=3),
            submitted_at=timezone.now(), proof_link="https://instagram.com/p/1",
            metrics_submitted_at=timezone.now(), views=100,
        )
        self.task_pending = models.MemberTask.objects.create(
            member_job=self.member_job, requirement=self.requirement,
            period_key="d2", period_start=today - timedelta(days=2),
            period_end=today - timedelta(days=2),
            submitted_at=timezone.now(), proof_link="https://instagram.com/p/2",
        )
        self.task_missed = models.MemberTask.objects.create(
            member_job=self.member_job, requirement=self.requirement,
            period_key="d3", period_start=today - timedelta(days=1),
            period_end=today - timedelta(days=1),
        )

    def test_jobs_pending_results_list(self):
        self.authenticate(self.member.user)
        response = self.client.get(f"/members/{self.member.uuid}/jobs/pending-results/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["uuid"] == str(self.member_job.uuid)
        assert data[0]["org"] == "KGAME99"
        assert data[0]["job_title"] == "Daily Posting Job"
        assert data[0]["pending_result_count"] == 1
        assert "payment_amount" not in data[0]
        assert "member" not in data[0]

    def test_job_pending_results_detail(self):
        self.authenticate(self.member.user)
        response = self.client.get(
            f"/members/{self.member.uuid}/jobs/{self.member_job.uuid}/pending-results/"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["org"] == "KGAME99"
        assert data["job_title"] == "Daily Posting Job"
        tasks = data["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["uuid"] == str(self.task_pending.uuid)
        assert tasks[0]["content_type"] == 2
        assert tasks[0]["platform"] == 1
        assert tasks[0]["day_number"] == 2
        assert "has_result" not in tasks[0]
        assert "period_start" not in tasks[0]

    def test_submitting_result_removes_it_from_pending(self):
        self.authenticate(self.member.user)
        response = self.client.post(
            f"/members/{self.member.uuid}/tasks/{self.task_pending.uuid}/result/",
            data={"views": 500},
            format="json",
        )
        assert response.status_code == 200

        response = self.client.get(
            f"/members/{self.member.uuid}/jobs/{self.member_job.uuid}/pending-results/"
        )
        assert response.json()["tasks"] == []

        response = self.client.get(f"/members/{self.member.uuid}/jobs/pending-results/")
        assert response.json() == []

    def test_missed_task_cannot_get_a_result(self):
        self.authenticate(self.member.user)
        response = self.client.post(
            f"/members/{self.member.uuid}/tasks/{self.task_missed.uuid}/result/",
            data={"views": 10},
            format="json",
        )
        assert response.status_code == 400

    def test_submitting_last_result_sends_completed_notification(self):
        self.authenticate(self.member.user)
        assert not Notification.objects.filter(
            recipient=self.member.user, notification_type=10,
        ).exists()

        response = self.client.post(
            f"/members/{self.member.uuid}/tasks/{self.task_pending.uuid}/result/",
            data={"views": 500},
            format="json",
        )
        assert response.status_code == 200

        notif = Notification.objects.filter(
            recipient=self.member.user, notification_type=10,
        ).first()
        assert notif is not None
        assert notif.message == "Daily Posting Job"

    def test_submitting_result_with_other_days_still_pending_sends_no_completed_notification(self):
        models.MemberTask.objects.create(
            member_job=self.member_job, requirement=self.requirement,
            period_key="d4", period_start=timezone.localdate(),
            period_end=timezone.localdate(),
            submitted_at=timezone.now(), proof_link="https://instagram.com/p/3",
        )

        self.authenticate(self.member.user)
        self.client.post(
            f"/members/{self.member.uuid}/tasks/{self.task_pending.uuid}/result/",
            data={"views": 500},
            format="json",
        )

        assert not Notification.objects.filter(
            recipient=self.member.user, notification_type=10,
        ).exists()


class ResultReminderTaskTest(BaseAPITestCase):
    def setUp(self):
        super().setUp()

        member_user = UserModel.objects.create(username="member_reminder")
        self.member = Member.objects.create(user=member_user, full_name="Member Reminder")

        company = models.Company.objects.create(name="REMIND-CO")
        self.job = models.Job.objects.create(
            company=company, title="Reminder Job",
            start_date=timezone.now() - timedelta(days=10),
        )
        requirement = models.JobRequirement.objects.create(
            job=self.job, platform=1, content_type=2, quantity=1,
        )
        self.member_job = models.MemberJob.objects.create(member=self.member, job=self.job)

        today = timezone.localdate()
        self.task = models.MemberTask.objects.create(
            member_job=self.member_job, requirement=requirement,
            period_key="r1", period_start=today - timedelta(days=1),
            period_end=today - timedelta(days=1),
            submitted_at=timezone.now(),
        )

    def test_sends_reminder_for_pending_jobs(self):
        send_pending_result_reminders()

        notif = Notification.objects.filter(
            recipient=self.member.user, notification_type=9,
        ).first()
        assert notif is not None
        assert "Reminder Job" in notif.message
        assert "1 day" in notif.message

    def test_no_reminder_once_result_submitted(self):
        self.task.submit_result(views=10)

        send_pending_result_reminders()

        assert not Notification.objects.filter(
            recipient=self.member.user, notification_type=9,
        ).exists()


class AdminResultAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        admin_models.Admin.objects.create(user=self.user, full_name="Base Admin")

        member_user = UserModel.objects.create(username="member_two")
        self.member = Member.objects.create(user=member_user, full_name="Member Two")

        self.company = models.Company.objects.create(name="ACEBET77")
        self.job = models.Job.objects.create(
            company=self.company,
            title="Weekly Job",
            start_date=timezone.now() - timedelta(days=10),
        )
        self.requirement = models.JobRequirement.objects.create(
            job=self.job, platform=2, content_type=1, quantity=1,
        )
        self.member_job = models.MemberJob.objects.create(
            member=self.member, job=self.job,
        )

        today = timezone.localdate()
        self.task_done = models.MemberTask.objects.create(
            member_job=self.member_job, requirement=self.requirement,
            period_key="d1", period_start=today - timedelta(days=2),
            period_end=today - timedelta(days=2),
            submitted_at=timezone.now(),
            metrics_submitted_at=timezone.now(), views=250, likes=30,
        )
        self.task_pending = models.MemberTask.objects.create(
            member_job=self.member_job, requirement=self.requirement,
            period_key="d2", period_start=today - timedelta(days=1),
            period_end=today - timedelta(days=1),
            submitted_at=timezone.now(),
        )

    def test_pending_list_for_job(self):
        self.authenticate()
        response = self.client.get(f"/jobs/job/{self.job.uuid}/result/pending/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["member_uuid"] == str(self.member.uuid)
        assert data[0]["pending_result_count"] == 1

    def test_member_results_for_job(self):
        self.authenticate()
        response = self.client.get(
            f"/jobs/job/{self.job.uuid}/result/member/{self.member.uuid}/"
        )
        assert response.status_code == 200
        tasks = response.json()["tasks"]
        assert len(tasks) == 2
        done_row = next(t for t in tasks if t["has_result"])
        assert done_row["views"] == 250
        assert done_row["likes"] == 30
        pending_row = next(t for t in tasks if not t["has_result"])
        assert "views" not in pending_row

    def test_requires_admin(self):
        self.authenticate(self.member.user)
        response = self.client.get(f"/jobs/job/{self.job.uuid}/result/pending/")
        assert response.status_code == 403
