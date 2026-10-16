from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.crmadmin import models as admin_models
from apps.earnings import models
from apps.jobs import models as job_models
from apps.members.models import Member
from apps.notifications.models import Notification
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


class JobPayoutAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()

        self.member_user = UserModel.objects.create(username="member_one")
        self.member = Member.objects.create(user=self.member_user)
        other_user = UserModel.objects.create(username="member_two")
        self.other_member = Member.objects.create(user=other_user)

        admin_user = UserModel.objects.create(username="admin_one")
        self.admin = admin_models.Admin.objects.create(user=admin_user)
        self.admin_user = admin_user

        self.company = job_models.Company.objects.create(name="KGAME99")
        self.job = self.make_job(
            start=timezone.now() - timedelta(days=10),
            end=timezone.now() - timedelta(days=2),
        )
        self.member_job = self.join(self.job, self.member)

    def make_job(self, start, end):
        job = job_models.Job.objects.create(
            company=self.company,
            title="Story Job",
            start_date=start,
            end_date=end,
            payment_amount=Decimal("50.00"),
            payment_period=3,
            status=2,
        )
        job_models.JobRequirement.objects.create(
            job=job, platform=1, content_type=2, quantity=1,
        )
        return job

    def join(self, job, member):
        return job_models.MemberJob.objects.create(
            member=member, job=job, status=2,
            joined=timezone.localdate() - timedelta(days=10),
        )

    def request_payout(self, member_job=None, member=None):
        self.authenticate((member or self.member).user)
        return self.client.post(
            f"/members/{(member or self.member).uuid}/job-payouts/",
            {"member_job_uuid": str((member_job or self.member_job).uuid)},
            format="json",
        )

    def test_request_after_job_end_is_created_pending(self):
        response = self.request_payout()

        self.assertEqual(response.status_code, 201)
        payout = models.JobPayout.objects.get()
        self.assertEqual(payout.status, 1)
        self.assertEqual(payout.member_job, self.member_job)

    def test_request_notifies_admins(self):
        self.request_payout()

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin_user, notification_type=11,
            ).exists()
        )

    def test_request_before_job_end_is_rejected(self):
        self.job.end_date = timezone.now() + timedelta(days=3)
        self.job.save()

        response = self.request_payout()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(models.JobPayout.objects.exists())

    def test_request_for_job_without_end_date_is_rejected(self):
        self.job.end_date = None
        self.job.save()

        response = self.request_payout()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(models.JobPayout.objects.exists())

    def test_second_request_for_same_job_is_rejected(self):
        self.request_payout()

        response = self.request_payout()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(models.JobPayout.objects.count(), 1)

    def test_request_blocked_while_approved_or_paid(self):
        self.request_payout()
        payout = models.JobPayout.objects.get()

        payout.approve(self.admin)
        self.assertEqual(self.request_payout().status_code, 400)

        payout.mark_paid()
        self.assertEqual(self.request_payout().status_code, 400)
        self.assertEqual(models.JobPayout.objects.count(), 1)

    def test_request_allowed_again_after_rejection(self):
        self.request_payout()
        models.JobPayout.objects.get().reject(self.admin, "Wrong bank")

        response = self.request_payout()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.JobPayout.objects.count(), 2)

    def test_database_blocks_second_live_payout_for_same_job(self):
        models.JobPayout.objects.create(member_job=self.member_job, amount=10)

        with self.assertRaises(IntegrityError), transaction.atomic():
            models.JobPayout.objects.create(member_job=self.member_job, amount=10)

    def test_member_cannot_request_for_another_members_job(self):
        response = self.request_payout(member=self.other_member)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(models.JobPayout.objects.exists())

    def test_member_cannot_act_as_another_member(self):
        self.authenticate(self.other_member.user)

        response = self.client.post(
            f"/members/{self.member.uuid}/job-payouts/",
            {"member_job_uuid": str(self.member_job.uuid)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(models.JobPayout.objects.exists())

    def test_amount_subtracts_deduction_for_missed_days(self):
        self.job.deduction_per_miss = Decimal("1.00")
        self.job.save()
        no_deduction = self.make_job(
            start=self.job.start_date, end=self.job.end_date,
        )
        no_deduction_job = self.join(no_deduction, self.other_member)

        self.request_payout()
        self.request_payout(no_deduction_job, self.other_member)

        with_deduction = models.JobPayout.objects.get(member_job=self.member_job)
        without = models.JobPayout.objects.get(member_job=no_deduction_job)
        self.assertLess(with_deduction.amount, without.amount)
        self.assertGreater(with_deduction.amount, 0)

    def test_jobs_listing_flags_button_state(self):
        ongoing = self.make_job(
            start=timezone.now() - timedelta(days=3),
            end=timezone.now() + timedelta(days=5),
        )
        self.join(ongoing, self.member)
        self.authenticate(self.member.user)

        response = self.client.get(f"/members/{self.member.uuid}/job-payouts/jobs/")

        self.assertEqual(response.status_code, 200)
        ended = next(r for r in response.data if r["member_job_uuid"] == str(self.member_job.uuid))
        open_row = next(r for r in response.data if r["member_job_uuid"] != str(self.member_job.uuid))
        self.assertTrue(ended["can_request"])
        self.assertFalse(open_row["can_request"])
        self.assertEqual(len(response.data), 2)

    def test_jobs_listing_shows_status_after_request(self):
        self.request_payout()
        self.authenticate(self.member.user)

        response = self.client.get(f"/members/{self.member.uuid}/job-payouts/jobs/")

        row = response.data[0]
        self.assertFalse(row["can_request"])
        self.assertEqual(row["payout_status"], 1)

    def test_admin_approve_then_mark_paid(self):
        self.request_payout()
        payout = models.JobPayout.objects.get()
        self.authenticate(self.admin_user)

        approved = self.client.patch(f"/earnings/job-payouts/{payout.uuid}/approve/")
        paid = self.client.patch(f"/earnings/job-payouts/{payout.uuid}/mark-paid/")

        self.assertEqual(approved.status_code, 200)
        self.assertEqual(paid.status_code, 200)
        payout.refresh_from_db()
        self.assertEqual(payout.status, 4)
        self.assertIsNotNone(payout.paid_at)
        self.assertEqual(payout.reviewed_by, self.admin)

    def test_admin_cannot_mark_paid_before_approval(self):
        self.request_payout()
        payout = models.JobPayout.objects.get()
        self.authenticate(self.admin_user)

        response = self.client.patch(f"/earnings/job-payouts/{payout.uuid}/mark-paid/")

        self.assertEqual(response.status_code, 400)
        payout.refresh_from_db()
        self.assertEqual(payout.status, 1)

    def test_admin_reject_requires_reason_and_notifies_member(self):
        self.request_payout()
        payout = models.JobPayout.objects.get()
        self.authenticate(self.admin_user)

        missing = self.client.patch(f"/earnings/job-payouts/{payout.uuid}/reject/", {}, format="json")
        rejected = self.client.patch(
            f"/earnings/job-payouts/{payout.uuid}/reject/",
            {"reject_reason": "Bank details missing"},
            format="json",
        )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(rejected.status_code, 200)
        payout.refresh_from_db()
        self.assertEqual(payout.status, 3)
        self.assertEqual(payout.reject_reason, "Bank details missing")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.member_user, notification_type=13,
            ).exists()
        )

    def test_admin_cannot_review_a_decided_request_twice(self):
        self.request_payout()
        payout = models.JobPayout.objects.get()
        self.authenticate(self.admin_user)
        self.client.patch(f"/earnings/job-payouts/{payout.uuid}/approve/")

        again = self.client.patch(f"/earnings/job-payouts/{payout.uuid}/approve/")
        reject = self.client.patch(
            f"/earnings/job-payouts/{payout.uuid}/reject/",
            {"reject_reason": "x"}, format="json",
        )

        self.assertEqual(again.status_code, 400)
        self.assertEqual(reject.status_code, 400)

    def test_member_cannot_use_admin_endpoints(self):
        self.request_payout()
        payout = models.JobPayout.objects.get()

        listing = self.client.get("/earnings/job-payouts/")
        approve = self.client.patch(f"/earnings/job-payouts/{payout.uuid}/approve/")

        self.assertEqual(listing.status_code, 403)
        self.assertEqual(approve.status_code, 403)

    def test_admin_list_filters_by_status(self):
        self.request_payout()
        self.authenticate(self.admin_user)

        pending = self.client.get("/earnings/job-payouts/?status=1")
        paid = self.client.get("/earnings/job-payouts/?status=4")

        self.assertEqual(pending.data["count"], 1)
        self.assertEqual(paid.data["count"], 0)
