from apps.admins import models as admin_models
from apps.members import models
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


class MemberAdminAPITest(BaseAPITestCase):
    """The admin-facing side of /members/."""

    def setUp(self):
        super().setUp()

        self.url = "/members"
        admin_models.Admin.objects.create(user=self.user, full_name="Base Admin")

        for i in range(1, 3):
            user = UserModel.objects.create(username=f"member_{i}")
            models.Member.objects.create(user=user, display_name=f"Member {i}")

    def test_list_requires_authentication(self):
        response = self.client.get(self.url + "/")
        assert response.status_code == 401

    def test_list(self):
        self.authenticate()
        response = self.client.get(self.url + "/")
        data = response.json()
        assert response.status_code == 200
        assert data["count"] == 2

    def test_create(self):
        self.authenticate()
        params = {
            "username": "new_member",
            "display_name": "New Member",
            "status": 1,
            "password": "NewPassword123",
            "confirm_password": "NewPassword123",
        }
        response = self.client.post(self.url + "/", data=params, format="json")
        data = response.json()
        assert response.status_code == 201
        assert data["username"] == "new_member"
        assert data["status"] == "ACTIVE"

        created = UserModel.objects.get(username="new_member")
        assert created.check_password("NewPassword123")

    def test_create_duplicate_username(self):
        self.authenticate()
        params = {
            "username": "member_1",
            "display_name": "Duplicate",
            "password": "NewPassword123",
            "confirm_password": "NewPassword123",
        }
        response = self.client.post(self.url + "/", data=params, format="json")
        assert response.status_code == 400

    def test_update(self):
        self.authenticate()
        target = models.Member.objects.first()
        response = self.client.put(
            self.url + f"/{target.uuid}/",
            data={"display_name": "Edited"},
            format="json",
        )
        data = response.json()
        assert response.status_code == 200
        assert data["display_name"] == "Edited"

    def test_archive(self):
        self.authenticate()
        target = models.Member.objects.first()
        url = self.url + f"/{target.uuid}/archive/"

        response = self.client.patch(url)
        assert response.status_code == 200

        response = self.client.get(self.url + "/")
        assert response.json()["count"] == 1

        response = self.client.patch(url)
        assert response.status_code == 400


class MemberProfileAPITest(BaseAPITestCase):
    """Requirement 4 — the member's own profile."""

    def setUp(self):
        super().setUp()

        self.url = "/members/profile"
        self.member = models.Member.objects.create(
            user=self.user,
            display_name="Eliska",
        )
        self.user.set_password("CurrentPass123")
        self.user.save()

    def test_get_profile(self):
        self.authenticate()
        response = self.client.get(self.url + "/")
        data = response.json()
        assert response.status_code == 200
        assert data["display_name"] == "Eliska"
        assert data["bank_details"] == []
        assert data["platform_accounts"] == []

    def test_patch_profile(self):
        self.authenticate()
        response = self.client.patch(
            self.url + "/", data={"display_name": "Eliska B"}, format="json"
        )
        data = response.json()
        assert response.status_code == 200
        assert data["display_name"] == "Eliska B"

    def test_change_password(self):
        self.authenticate()
        params = {
            "current_password": "CurrentPass123",
            "password": "BrandNew123",
            "confirm_password": "BrandNew123",
        }
        response = self.client.patch(
            self.url + "/change-password/", data=params, format="json"
        )
        assert response.status_code == 200

        self.user.refresh_from_db()
        assert self.user.check_password("BrandNew123")

    def test_change_password_wrong_current(self):
        self.authenticate()
        params = {
            "current_password": "WrongPass",
            "password": "BrandNew123",
            "confirm_password": "BrandNew123",
        }
        response = self.client.patch(
            self.url + "/change-password/", data=params, format="json"
        )
        assert response.status_code == 400

    def test_bank_details(self):
        self.authenticate()
        url = self.url + "/bank-details/"

        params = {
            "bank": 2,
            "account_holder_name": "Eliska Beatrice Daulis",
            "account_number": "1234567890",
            "is_primary": True,
        }
        response = self.client.post(url, data=params, format="json")
        data = response.json()
        assert response.status_code == 201
        assert data["bank"] == "CIMB Bank"
        assert data["is_primary"] is True

        params["bank"] = 1
        params["account_number"] = "9999999999"
        response = self.client.post(url, data=params, format="json")
        assert response.status_code == 201

        primary_count = models.BankDetail.objects.filter(
            member=self.member, is_primary=True, archived=None,
        ).count()
        assert primary_count == 1

        response = self.client.get(url)
        assert response.json()["count"] == 2

    def test_platform_accounts(self):
        self.authenticate()
        url = self.url + "/platform-accounts/"

        response = self.client.post(
            url, data={"platform": 2, "handle": "@eliska"}, format="json"
        )
        data = response.json()
        assert response.status_code == 201
        assert data["platform"] == "TIKTOK"

        response = self.client.post(
            url, data={"platform": 2, "handle": "@eliska2"}, format="json"
        )
        assert response.status_code == 400

    def test_audit_log(self):
        self.authenticate()
        models.LoginAudit.objects.create(
            member=self.member, ip_address="127.0.0.1", device="Chrome",
        )
        response = self.client.get(self.url + "/audit-log/")
        data = response.json()
        assert response.status_code == 200
        assert data["count"] == 1
        assert data["results"][0]["device"] == "Chrome"
