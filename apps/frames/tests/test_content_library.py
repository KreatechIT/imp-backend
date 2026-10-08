from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.crmadmin.models import Admin
from apps.frames import models
from apps.jobs.models import Company, Job
from apps.members.models import Member
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel

CONTENT_URL = "/frame/content/"


class ContentLibraryUploaderTest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = UserModel.objects.create(username="library_admin")
        Admin.objects.create(user=self.admin_user, full_name="Library Admin")

        company = Company.objects.create(name="Acme")
        job = Job.objects.create(company=company, title="Job", start_date=timezone.now())
        self.frame = models.Frame.objects.create(
            job=job,
            name="Frame",
            image=SimpleUploadedFile("frame.png", b"png", content_type="image/png"),
        )

    def upload_for(self, member):
        return models.RenderedContent.objects.create(
            frame=self.frame,
            member=member,
            original_file=SimpleUploadedFile("clip.mp4", b"video", content_type="video/mp4"),
            media_type=1,
        )

    def first_row(self):
        self.authenticate(self.admin_user)
        response = self.client.get(CONTENT_URL)
        assert response.status_code == 200, response.content
        return response.json()["results"][0]

    def test_uploader_name_is_shown(self):
        member = Member.objects.create(
            user=self.user, full_name="Aiman Hakim", phone_number="0123456789",
        )
        self.upload_for(member)

        row = self.first_row()
        assert row["member"] == "Aiman Hakim"
        assert row["username"] == "john_doe"
        assert row["phone_number"] == "0123456789"

    def test_falls_back_to_username_when_member_has_no_full_name(self):
        member = Member.objects.create(user=self.user)
        self.upload_for(member)

        row = self.first_row()
        assert row["member"] == "john_doe"
        assert row["username"] == "john_doe"
        assert row["phone_number"] is None
