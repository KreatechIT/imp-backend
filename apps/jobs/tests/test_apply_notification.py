from django.utils import timezone

from apps.crmadmin import models as admin_models
from apps.jobs import models
from apps.members.models import Member
from apps.notifications.models import Notification
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


class ApplyNotificationAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        admin_user = UserModel.objects.create(username="admin_one")
        self.admin = admin_models.Admin.objects.create(user=admin_user, full_name="Admin One")

        member_user = UserModel.objects.create(username="member_one")
        self.member = Member.objects.create(user=member_user, full_name="Member One")

        company = models.Company.objects.create(name="EP369")
        self.job = models.Job.objects.create(
            company=company, title="Post Story 1 Hari", status=2, start_date=timezone.now(),
        )

        self.url = f"/members/{self.member.uuid}/available-jobs/{self.job.uuid}/apply/"
        self.authenticate(member_user)

    def test_applying_notifies_admins(self):
        response = self.client.post(self.url)
        assert response.status_code == 201

        notification = Notification.objects.get(recipient=self.admin.user)
        assert notification.notification_type == 18
        assert notification.role == 1
        assert notification.message == "Member One (@member_one) applied to Post Story 1 Hari"

    def test_duplicate_application_does_not_notify_again(self):
        self.client.post(self.url)
        response = self.client.post(self.url)
        assert response.status_code != 201
        assert Notification.objects.filter(notification_type=18).count() == 1
