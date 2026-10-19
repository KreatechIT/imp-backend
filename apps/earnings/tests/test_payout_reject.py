from apps.crmadmin import models as admin_models
from apps.earnings import models
from apps.members.models import Member
from apps.notifications.models import Notification
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


class PayoutRejectAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.member_user = UserModel.objects.create(username="member_one")
        self.member = Member.objects.create(user=self.member_user)
        self.admin_user = UserModel.objects.create(username="admin_one")
        admin_models.Admin.objects.create(user=self.admin_user)
        self.payout = models.Payout.objects.create(
            member=self.member, period_key="2026-10", amount=60,
        )

    def reject(self, body):
        self.authenticate(self.admin_user)
        return self.client.patch(
            f"/earnings/payouts/{self.payout.uuid}/reject/", body, format="json",
        )

    def test_reject_requires_reason(self):
        self.assertEqual(self.reject({}).status_code, 400)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, 1)

    def test_reject_sets_status_and_notifies_member(self):
        response = self.reject({"reject_reason": "Suspected fraud"})

        self.assertEqual(response.status_code, 200)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, 3)
        self.assertEqual(self.payout.reject_reason, "Suspected fraud")
        self.assertTrue(
            Notification.objects.filter(recipient=self.member_user, notification_type=13).exists()
        )

    def test_rejected_payout_cannot_be_rejected_or_paid(self):
        self.reject({"reject_reason": "Suspected fraud"})

        self.assertEqual(self.reject({"reject_reason": "Again"}).status_code, 400)
        self.authenticate(self.admin_user)
        paid = self.client.patch(f"/earnings/payouts/{self.payout.uuid}/mark-paid/")
        self.assertEqual(paid.status_code, 400)

    def test_rejected_listed_under_status_3_not_pending(self):
        self.reject({"reject_reason": "Suspected fraud"})

        self.authenticate(self.admin_user)
        pending = self.client.get("/earnings/payouts/?status=1").json()
        rejected = self.client.get("/earnings/payouts/?status=3").json()
        self.assertEqual(len(pending["results"]), 0)
        self.assertEqual(len(rejected["results"]), 1)

    def test_same_period_can_be_requested_again_after_rejection(self):
        self.reject({"reject_reason": "Suspected fraud"})

        models.Payout.objects.create(member=self.member, period_key="2026-10", amount=60)
