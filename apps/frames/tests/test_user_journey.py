import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image, ImageDraw
from rest_framework.test import APITestCase

from apps.crmadmin.models import Admin
from apps.frames import models
from apps.jobs.models import Company, Job, MemberJob
from apps.members.models import Member, Role, UserGroup
from base.models import UserModel


def overlay():
    img = Image.new("RGBA", (120, 180), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle([0, 0, 119, 179], outline=(255, 0, 128, 255), width=10)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile("overlay.png", buf.read(), content_type="image/png")


def background():
    buf = io.BytesIO()
    Image.new("RGB", (120, 180), (20, 20, 60)).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile("bg.png", buf.read(), content_type="image/png")


def photo():
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (30, 130, 220)).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile("photo.png", buf.read(), content_type="image/png")


class PostDeskJourneyTest(APITestCase):
    """Admin sets up a KOC and a frame; the KOC then uses it."""

    def setUp(self):
        self.admin_user = UserModel.objects.create(username="journey_admin")
        Admin.objects.create(user=self.admin_user, full_name="Admin")
        self.client.force_authenticate(user=self.admin_user)

        Role.objects.get_or_create(name="influencer")
        Role.objects.get_or_create(name="koc")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_admin_sets_up_koc_then_koc_uses_frame(self):
        koc_role = self.client.get("/members/roles/").json()["results"]
        koc_uuid = next(r["uuid"] for r in koc_role if r["name"] == "koc")

        created = self.client.post(
            "/members/",
            data={
                "username": "journey_koc",
                "password": "pw-12345",
                "confirm_password": "pw-12345",
                "full_name": "Journey Koc",
                "role_uuid": koc_uuid,
            },
            format="json",
        )
        assert created.status_code == 201, created.content
        assert created.json()["member_role"] == "koc"
        member_uuid = created.json()["uuid"]

        group = self.client.post(
            "/members/group/",
            data={"name": "Journey Group", "members": [member_uuid]},
            format="json",
        )
        assert group.status_code == 201, group.content
        assert group.json()["total_members"] == 1

        frame = self.client.post(
            "/frame/library/",
            data={
                "name": "Journey Frame",
                "frame_type": 2,
                "background": background(),
                "image": overlay(),
                "user_groups": [group.json()["uuid"]],
            },
            format="multipart",
        )
        assert frame.status_code == 201, frame.content
        frame_uuid = frame.json()["uuid"]

        listed = self.client.get("/frame/postdesk/").json()["results"]
        assert [f["name"] for f in listed] == ["Journey Frame"]
        assert listed[0]["user_groups"][0]["name"] == "Journey Group"

        self.client.force_authenticate(user=None)
        self.client.credentials()
        login = self.client.post(
            "/login/member-access-token/",
            data={"username": "journey_koc", "password": "pw-12345"},
            format="json",
        )
        assert login.status_code == 200, login.content
        assert login.json()["member_role"] == "koc"
        assert login.json()["role"] == "MEMBER"

        token = login.json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        rendered = self.client.post(
            f"/frame/{frame_uuid}/render/",
            data={"file": photo()},
            format="multipart",
        )
        assert rendered.status_code == 201, rendered.content
        render_uuid = rendered.json()["uuid"]

        row = models.RenderedContent.objects.get(uuid=render_uuid)
        assert row.render_status == 2
        assert row.rendered_file

        downloaded = self.client.post(
            f"/frame/{frame_uuid}/render/{render_uuid}/downloaded/"
        )
        assert downloaded.status_code == 200, downloaded.content

        row.refresh_from_db()
        assert not row.rendered_file

    def test_koc_cannot_reach_admin_modules(self):
        koc_user = UserModel.objects.create(username="journey_koc2")
        Member.objects.create(
            user=koc_user, full_name="Koc Two", role=Role.objects.get(name="koc"),
        )

        self.client.force_authenticate(user=koc_user)

        assert self.client.get("/members/").status_code == 403
        assert self.client.get("/members/roles/").status_code == 403
        assert self.client.get("/members/group/").status_code == 403
        assert self.client.get("/frame/postdesk/").status_code == 403
        assert self.client.get("/frame/content/").status_code == 403


class ImpJourneyTest(APITestCase):
    """The existing influencer flow must still work end to end."""

    def setUp(self):
        self.admin_user = UserModel.objects.create(username="imp_admin")
        Admin.objects.create(user=self.admin_user, full_name="Admin")
        self.client.force_authenticate(user=self.admin_user)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_admin_creates_job_frame_then_member_renders(self):
        company = Company.objects.create(name="Journey Co")
        job = Job.objects.create(
            company=company, title="Journey Job", start_date=timezone.now(),
        )

        frame = self.client.post(
            f"/jobs/org/{company.uuid}/job/{job.uuid}/frames/",
            data={
                "name": "Campaign Frame",
                "job_uuid": str(job.uuid),
                "image": overlay(),
            },
            format="multipart",
        )
        assert frame.status_code == 201, frame.content
        frame_uuid = frame.json()["uuid"]
        assert frame.json()["job_title"] == "Journey Job"

        member_user = UserModel.objects.create(username="imp_member")
        member_user.set_password("pw-12345")
        member_user.save()
        member = Member.objects.create(user=member_user, full_name="Imp Member")
        MemberJob.objects.create(member=member, job=job, status=2)

        self.client.force_authenticate(user=member_user)

        editor = self.client.get(
            f"/members/{member.uuid}/jobs/{job.uuid}/frames/"
        )
        assert editor.status_code == 200
        assert [f["name"] for f in editor.json()["results"]] == ["Campaign Frame"]

        rendered = self.client.post(
            f"/frame/{frame_uuid}/render/",
            data={"file": photo()},
            format="multipart",
        )
        assert rendered.status_code == 201, rendered.content

        row = models.RenderedContent.objects.get(uuid=rendered.json()["uuid"])
        assert row.render_status == 2
        assert row.rendered_file
