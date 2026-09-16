import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.crmadmin.models import Admin
from apps.frames import models
from apps.jobs.models import Company, Job, MemberJob
from apps.members.models import Member, UserGroup
from base.base_test_classes import BaseAPITestCase
from base.models import UserModel


def overlay_upload(name="overlay.png"):
    img = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle([0, 0, 199, 299], outline=(255, 0, 128, 255), width=15)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


def background_upload(name="background.png"):
    buf = io.BytesIO()
    Image.new("RGB", (200, 300), (20, 20, 60)).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


class FrameAPIBaseTest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = UserModel.objects.create(username="frame_admin")
        Admin.objects.create(user=self.admin_user, full_name="Frame Admin")

        self.company = Company.objects.create(name="Acme")
        self.job = Job.objects.create(
            company=self.company, title="Job One", start_date=timezone.now(),
        )
        self.other_job = Job.objects.create(
            company=self.company, title="Job Two", start_date=timezone.now(),
        )

        self.member = Member.objects.create(user=self.user, full_name="Koc One")
        self.other_user = UserModel.objects.create(username="koc_two")
        self.other_member = Member.objects.create(
            user=self.other_user, full_name="Koc Two",
        )
        self.group = UserGroup.objects.create(name="Group Alpha")
        self.group.members.add(self.member)

        self.authenticate(self.admin_user)

    def create_job_frame(self, name="Job Frame", job=None):
        return self.client.post(
            "/frame/library/",
            data={
                "name": name,
                "job_uuid": str((job or self.job).uuid),
                "image": overlay_upload(),
            },
            format="multipart",
        )

    def create_postdesk_frame(self, name="PostDesk Frame", **extra):
        data = {
            "name": name,
            "frame_type": 2,
            "background": background_upload(),
            "image": overlay_upload(),
        }
        data.update(extra)
        return self.client.post("/frame/library/", data=data, format="multipart")


class JobFrameTest(FrameAPIBaseTest):
    def test_create_via_library(self):
        response = self.create_job_frame()
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["frame_type"] == 1
        assert data["job_title"] == "Job One"
        assert data["org"] == "Acme"
        assert data["background"] is None

        frame = models.Frame.objects.get(uuid=data["uuid"])
        assert frame.assignments.count() == 1
        assert frame.assignments.first().job_id == self.job.id

    def test_create_via_nested_job_route(self):
        response = self.client.post(
            f"/jobs/org/{self.company.uuid}/job/{self.job.uuid}/frames/",
            data={
                "name": "Nested Frame",
                "job_uuid": str(self.job.uuid),
                "image": overlay_upload(),
            },
            format="multipart",
        )
        assert response.status_code == 201, response.content
        assert response.json()["frame_type"] == 1
        assert response.json()["job_title"] == "Job One"

    def test_job_uuid_is_required(self):
        response = self.client.post(
            "/frame/library/",
            data={"name": "No Job", "image": overlay_upload()},
            format="multipart",
        )
        assert response.status_code == 400
        assert "job_uuid" in response.json()["details"]

    def test_image_is_required(self):
        response = self.client.post(
            "/frame/library/",
            data={"name": "No Image", "job_uuid": str(self.job.uuid)},
            format="multipart",
        )
        assert response.status_code == 400
        assert "image" in response.json()["details"]

    def test_unknown_job_is_rejected(self):
        response = self.client.post(
            "/frame/library/",
            data={
                "name": "Bad Job",
                "job_uuid": "00000000-0000-0000-0000-000000000000",
                "image": overlay_upload(),
            },
            format="multipart",
        )
        assert response.status_code == 400

    def test_list_excludes_postdesk_frames(self):
        self.create_job_frame(name="Job Only")
        self.create_postdesk_frame(name="Hidden PostDesk")

        names = [f["name"] for f in self.client.get("/frame/library/").json()["results"]]
        assert "Job Only" in names
        assert "Hidden PostDesk" not in names

    def test_filter_by_job(self):
        self.create_job_frame(name="On Job One", job=self.job)
        self.create_job_frame(name="On Job Two", job=self.other_job)

        response = self.client.get(f"/frame/library/?job_uuid={self.job.uuid}")
        names = [f["name"] for f in response.json()["results"]]
        assert names == ["On Job One"]

    def test_update_name_and_reassign_job(self):
        uuid = self.create_job_frame().json()["uuid"]

        response = self.client.patch(
            f"/frame/library/{uuid}/",
            data={"name": "Renamed", "job_uuid": str(self.other_job.uuid)},
            format="json",
        )
        assert response.status_code == 200, response.content
        assert response.json()["name"] == "Renamed"
        assert response.json()["job_title"] == "Job Two"

    def test_archive(self):
        uuid = self.create_job_frame().json()["uuid"]

        assert self.client.patch(f"/frame/library/{uuid}/archive/").status_code == 200
        assert self.client.patch(f"/frame/library/{uuid}/archive/").status_code == 400

        names = [f["name"] for f in self.client.get("/frame/library/").json()["results"]]
        assert "Job Frame" not in names


class PostDeskFrameTest(FrameAPIBaseTest):
    def test_create_with_both_layers(self):
        response = self.create_postdesk_frame()
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["frame_type"] == 2
        assert data["job_uuid"] is None
        assert data["background"] and data["image"]

    def test_create_with_background_only(self):
        response = self.client.post(
            "/frame/library/",
            data={
                "name": "Background Only",
                "frame_type": 2,
                "background": background_upload(),
            },
            format="multipart",
        )
        assert response.status_code == 201, response.content
        assert response.json()["image"] is None

    def test_create_with_overlay_only(self):
        response = self.client.post(
            "/frame/library/",
            data={
                "name": "Overlay Only",
                "frame_type": 2,
                "image": overlay_upload(),
            },
            format="multipart",
        )
        assert response.status_code == 201, response.content
        assert response.json()["background"] is None

    def test_create_without_any_layer_is_rejected(self):
        response = self.client.post(
            "/frame/library/",
            data={"name": "Empty", "frame_type": 2},
            format="multipart",
        )
        assert response.status_code == 400
        assert "background" in response.json()["details"]

    def test_assign_to_members_and_groups(self):
        response = self.create_postdesk_frame(
            members=[str(self.member.uuid), str(self.other_member.uuid)],
            user_groups=[str(self.group.uuid)],
        )
        assert response.status_code == 201, response.content

        detail = self.client.get(
            f"/frame/postdesk/{response.json()['uuid']}/"
        ).json()
        assert detail["total_assigned"] == 3
        assert sorted(m["username"] for m in detail["members"]) == [
            "john_doe", "koc_two",
        ]
        assert [g["name"] for g in detail["user_groups"]] == ["Group Alpha"]

    def test_assignment_rows_have_single_target(self):
        uuid = self.create_postdesk_frame(
            members=[str(self.member.uuid)],
            user_groups=[str(self.group.uuid)],
        ).json()["uuid"]

        for assignment in models.Frame.objects.get(uuid=uuid).assignments.all():
            targets = [assignment.job_id, assignment.member_id, assignment.user_group_id]
            assert len([t for t in targets if t is not None]) == 1

    def test_unknown_member_is_rejected(self):
        response = self.create_postdesk_frame(
            members=["00000000-0000-0000-0000-000000000000"],
        )
        assert response.status_code == 400
        assert "does not exist" in response.json()["details"]

    def test_unknown_group_is_rejected(self):
        response = self.create_postdesk_frame(
            user_groups=["00000000-0000-0000-0000-000000000000"],
        )
        assert response.status_code == 400

    def test_archived_member_is_rejected(self):
        self.other_member.archive()
        response = self.create_postdesk_frame(members=[str(self.other_member.uuid)])
        assert response.status_code == 400

    def test_list_excludes_job_frames(self):
        self.create_job_frame(name="Job Hidden")
        self.create_postdesk_frame(name="PostDesk Shown")

        names = [f["name"] for f in self.client.get("/frame/postdesk/").json()["results"]]
        assert names == ["PostDesk Shown"]

    def test_list_includes_assignments(self):
        self.create_postdesk_frame(members=[str(self.member.uuid)])

        row = self.client.get("/frame/postdesk/").json()["results"][0]
        assert row["total_assigned"] == 1
        assert row["members"][0]["full_name"] == "Koc One"

    def test_filter_by_name(self):
        self.create_postdesk_frame(name="Spring Neon")
        self.create_postdesk_frame(name="Winter Glow")

        response = self.client.get("/frame/postdesk/?name=spring")
        assert [f["name"] for f in response.json()["results"]] == ["Spring Neon"]

    def test_reassign_replaces_previous_targets(self):
        uuid = self.create_postdesk_frame(
            members=[str(self.member.uuid)],
            user_groups=[str(self.group.uuid)],
        ).json()["uuid"]

        response = self.client.patch(
            f"/frame/library/{uuid}/",
            data={"members": [str(self.other_member.uuid)], "user_groups": []},
            format="json",
        )
        assert response.status_code == 200, response.content

        detail = self.client.get(f"/frame/postdesk/{uuid}/").json()
        assert [m["username"] for m in detail["members"]] == ["koc_two"]
        assert detail["user_groups"] == []

    def test_patch_without_assignments_keeps_them(self):
        uuid = self.create_postdesk_frame(
            members=[str(self.member.uuid)],
        ).json()["uuid"]

        response = self.client.patch(
            f"/frame/library/{uuid}/", data={"name": "Just Renamed"}, format="json",
        )
        assert response.status_code == 200, response.content

        detail = self.client.get(f"/frame/postdesk/{uuid}/").json()
        assert detail["name"] == "Just Renamed"
        assert [m["username"] for m in detail["members"]] == ["john_doe"]

    def test_archive(self):
        uuid = self.create_postdesk_frame().json()["uuid"]

        assert self.client.patch(f"/frame/library/{uuid}/archive/").status_code == 200
        assert self.client.get("/frame/postdesk/").json()["count"] == 0

    def test_one_member_can_hold_several_frames(self):
        first = self.create_postdesk_frame(
            name="Frame X", members=[str(self.member.uuid)],
        )
        second = self.create_postdesk_frame(
            name="Frame Y", members=[str(self.member.uuid)],
        )
        assert first.status_code == 201, first.content
        assert second.status_code == 201, second.content

        assigned = models.FrameAssignment.objects.filter(
            member=self.member, archived=None,
        )
        assert assigned.count() == 2
        assert sorted(a.frame.name for a in assigned) == ["Frame X", "Frame Y"]

    def test_frame_type_cannot_be_changed(self):
        uuid = self.create_postdesk_frame().json()["uuid"]

        response = self.client.patch(
            f"/frame/library/{uuid}/", data={"frame_type": 1}, format="json",
        )
        assert response.status_code == 200, response.content
        assert models.Frame.objects.get(uuid=uuid).frame_type == 2


class FrameTypeValidationTest(FrameAPIBaseTest):
    def test_job_frame_rejects_members(self):
        response = self.client.post(
            "/frame/library/",
            data={
                "name": "Bad",
                "job_uuid": str(self.job.uuid),
                "image": overlay_upload(),
                "members": [str(self.member.uuid)],
            },
            format="multipart",
        )
        assert response.status_code == 400
        assert "members" in response.json()["details"]

    def test_job_frame_rejects_background(self):
        response = self.client.post(
            "/frame/library/",
            data={
                "name": "Bad",
                "job_uuid": str(self.job.uuid),
                "image": overlay_upload(),
                "background": background_upload(),
            },
            format="multipart",
        )
        assert response.status_code == 400
        assert "background" in response.json()["details"]

    def test_postdesk_frame_rejects_job_uuid(self):
        response = self.client.post(
            "/frame/library/",
            data={
                "name": "Bad",
                "frame_type": 2,
                "job_uuid": str(self.job.uuid),
                "background": background_upload(),
            },
            format="multipart",
        )
        assert response.status_code == 400
        assert "job_uuid" in response.json()["details"]

    def test_patch_job_frame_with_members_is_rejected(self):
        uuid = self.create_job_frame().json()["uuid"]

        response = self.client.patch(
            f"/frame/library/{uuid}/",
            data={"members": [str(self.member.uuid)]},
            format="json",
        )
        assert response.status_code == 400

    def test_patch_postdesk_frame_with_job_uuid_is_rejected(self):
        uuid = self.create_postdesk_frame().json()["uuid"]

        response = self.client.patch(
            f"/frame/library/{uuid}/",
            data={"job_uuid": str(self.job.uuid)},
            format="json",
        )
        assert response.status_code == 400


class FrameMediaUrlTest(FrameAPIBaseTest):
    def test_job_frame_returns_absolute_image_url(self):
        data = self.create_job_frame().json()
        assert data["image"].startswith("http://testserver/media/")

    def test_postdesk_frame_returns_absolute_urls(self):
        data = self.create_postdesk_frame().json()
        assert data["background"].startswith("http://testserver/media/")
        assert data["image"].startswith("http://testserver/media/")

    def test_list_returns_absolute_urls(self):
        self.create_postdesk_frame()
        row = self.client.get("/frame/postdesk/").json()["results"][0]
        assert row["background"].startswith("http://testserver/media/")
        assert row["image"].startswith("http://testserver/media/")


class FramePermissionTest(FrameAPIBaseTest):
    def test_postdesk_list_requires_authentication(self):
        self.client.credentials()
        assert self.client.get("/frame/postdesk/").status_code == 401

    def test_postdesk_list_rejects_non_admin(self):
        self.authenticate(self.user)
        assert self.client.get("/frame/postdesk/").status_code == 403


class RenderAuthorizationTest(FrameAPIBaseTest):
    def render(self, frame_uuid):
        return self.client.post(
            f"/frame/{frame_uuid}/render/",
            data={"file": overlay_upload("content.png")},
            format="multipart",
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_member_can_render_on_their_own_job_frame(self):
        uuid = self.create_job_frame(job=self.job).json()["uuid"]
        MemberJob.objects.create(member=self.member, job=self.job, status=2)

        self.authenticate(self.user)
        assert self.render(uuid).status_code == 201

    def test_member_cannot_render_on_another_jobs_frame(self):
        uuid = self.create_job_frame(job=self.other_job).json()["uuid"]
        MemberJob.objects.create(member=self.member, job=self.job, status=2)

        self.authenticate(self.user)
        assert self.render(uuid).status_code == 400

    def test_member_cannot_render_on_unassigned_postdesk_frame(self):
        uuid = self.create_postdesk_frame().json()["uuid"]
        MemberJob.objects.create(member=self.member, job=self.job, status=2)

        self.authenticate(self.user)
        assert self.render(uuid).status_code == 400

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_member_can_render_on_postdesk_frame_assigned_to_them(self):
        uuid = self.create_postdesk_frame(
            members=[str(self.member.uuid)],
        ).json()["uuid"]

        self.authenticate(self.user)
        assert self.render(uuid).status_code == 201

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_member_can_render_on_postdesk_frame_assigned_to_their_group(self):
        uuid = self.create_postdesk_frame(
            user_groups=[str(self.group.uuid)],
        ).json()["uuid"]

        self.authenticate(self.user)
        assert self.render(uuid).status_code == 201

    def test_member_not_in_group_cannot_render_group_frame(self):
        uuid = self.create_postdesk_frame(
            user_groups=[str(self.group.uuid)],
        ).json()["uuid"]

        self.authenticate(self.other_user)
        assert self.render(uuid).status_code == 400

    def test_member_cannot_render_on_job_frame_when_not_active_on_job(self):
        uuid = self.create_job_frame(job=self.job).json()["uuid"]
        MemberJob.objects.create(member=self.member, job=self.job, status=1)

        self.authenticate(self.user)
        assert self.render(uuid).status_code == 400


class MemberFrameAccessTest(FrameAPIBaseTest):
    def test_member_sees_only_frames_for_jobs_they_hold(self):
        self.create_job_frame(name="Mine", job=self.job)
        self.create_job_frame(name="Theirs", job=self.other_job)
        MemberJob.objects.create(member=self.member, job=self.job, status=2)

        self.authenticate(self.user)

        own = self.client.get(
            f"/members/{self.member.uuid}/jobs/{self.job.uuid}/frames/"
        ).json()
        assert [f["name"] for f in own["results"]] == ["Mine"]

        other = self.client.get(
            f"/members/{self.member.uuid}/jobs/{self.other_job.uuid}/frames/"
        ).json()
        assert other["results"] == []

    def test_member_does_not_see_postdesk_frames_on_a_job(self):
        self.create_postdesk_frame(members=[str(self.member.uuid)])
        MemberJob.objects.create(member=self.member, job=self.job, status=2)

        self.authenticate(self.user)
        response = self.client.get(
            f"/members/{self.member.uuid}/jobs/{self.job.uuid}/frames/"
        )
        assert response.json()["results"] == []
