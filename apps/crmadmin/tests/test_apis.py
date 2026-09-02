from apps.crmadmin import models
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


class AdminAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()

        self.url = "/admins"
        self.admin = models.Admin.objects.create(
            user=self.user,
            full_name="Base Admin",
        )

        for i in range(1, 3):
            user = UserModel.objects.create(username=f"admin_{i}")
            models.Admin.objects.create(user=user, full_name=f"Admin {i}")

    def test_list_requires_admin(self):
        response = self.client.get(self.url + "/users/")
        assert response.status_code == 401

    def test_list(self):
        self.authenticate()
        response = self.client.get(self.url + "/users/")
        data = response.json()
        assert response.status_code == 200
        assert data["count"] == 3

    def test_create(self):
        self.authenticate()
        params = {
            "username": "new_admin",
            "full_name": "New Admin",
            "status": 1,
            "password": "NewPassword123",
            "confirm_password": "NewPassword123",
        }
        response = self.client.post(self.url + "/users/", data=params, format="json")
        data = response.json()
        assert response.status_code == 201
        assert data["username"] == "new_admin"
        assert data["status"] == "ACTIVE"

        created = UserModel.objects.get(username="new_admin")
        assert created.check_password("NewPassword123")

    def test_create_password_mismatch(self):
        self.authenticate()
        params = {
            "username": "mismatch",
            "full_name": "Mismatch",
            "password": "one",
            "confirm_password": "two",
        }
        response = self.client.post(self.url + "/users/", data=params, format="json")
        assert response.status_code == 400
        assert "confirm_password" in response.json()["details"]

    def test_create_duplicate_username(self):
        self.authenticate()
        params = {
            "username": "admin_1",
            "full_name": "Duplicate",
            "password": "NewPassword123",
            "confirm_password": "NewPassword123",
        }
        response = self.client.post(self.url + "/users/", data=params, format="json")
        assert response.status_code == 400

    def test_update(self):
        self.authenticate()
        url = self.url + f"/users/{self.admin.uuid}/"
        response = self.client.put(url, data={"full_name": "Edited"}, format="json")
        data = response.json()
        assert response.status_code == 200
        assert data["full_name"] == "Edited"

    def test_reset_password(self):
        self.authenticate()
        url = self.url + f"/users/{self.admin.uuid}/resetpassword/"
        params = {"password": "Rotated123", "confirm_password": "Rotated123"}
        response = self.client.patch(url, data=params, format="json")
        assert response.status_code == 200

        self.user.refresh_from_db()
        assert self.user.check_password("Rotated123")

    def test_archive(self):
        self.authenticate()
        target = models.Admin.objects.exclude(pk=self.admin.pk).first()
        url = self.url + f"/users/{target.uuid}/archive/"

        response = self.client.patch(url)
        assert response.status_code == 200

        target.refresh_from_db()
        assert target.is_archived

        response = self.client.get(self.url + "/users/")
        assert response.json()["count"] == 2

        response = self.client.patch(url)
        assert response.status_code == 400

    def test_activity_log(self):
        self.authenticate()
        models.ActivityLog.objects.create(admin=self.admin, activity="Logged in")

        response = self.client.get(self.url + "/activity-log/")
        data = response.json()
        assert response.status_code == 200
        assert data["count"] == 1
        assert data["results"][0]["activity"] == "Logged in"
