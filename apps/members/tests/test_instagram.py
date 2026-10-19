from apps.crmadmin import models as admin_models
from apps.members.models import Member
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


class InstagramLinkAPITest(BaseAPITestCase):
    def test_admin_create_and_update_and_member_edit(self):
        admin_models.Admin.objects.create(user=self.user, full_name="Base Admin")
        self.authenticate()

        created = self.client.post("/members/", data={
            "username": "koc_one", "password": "NewPassword123", "confirm_password": "NewPassword123",
            "instagram_url": "https://www.instagram.com/koc_one/", "facebook_url": "https://facebook.com/koc.one",
        }, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["instagram_url"], "https://www.instagram.com/koc_one/")

        self.assertEqual(created.json()["facebook_url"], "https://facebook.com/koc.one")
        member_uuid = created.json()["uuid"]
        updated = self.client.patch(f"/members/{member_uuid}/", {"instagram_url": "https://www.instagram.com/new/", "facebook_url": ""}, format="json")
        self.assertEqual(updated.json()["instagram_url"], "https://www.instagram.com/new/")
        self.assertEqual(updated.json()["facebook_url"], "")

        member = Member.objects.get(uuid=member_uuid)
        self.authenticate(member.user)
        own = self.client.patch("/members/profile/", {"instagram_url": "https://www.instagram.com/mine/", "facebook_url": "https://facebook.com/mine"}, format="json")
        self.assertEqual(own.json()["instagram_url"], "https://www.instagram.com/mine/")
        self.assertEqual(own.json()["facebook_url"], "https://facebook.com/mine")
