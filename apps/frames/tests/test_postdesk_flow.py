"""New coverage for this session's PostDesk work: SourceVideo upload/pull,
MemberPostDeskFrameViewSet visibility rules, PostDeskRenderViewSet create
with every background/overlay combination, caption fields end-to-end, the
layer-order compositing geometry, and the frame_type=1 vs frame_type=2
render-lifecycle distinctions (expiry task, downloaded action).
"""
import io
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.frames import models
from apps.frames.tasks import _caption_filter, _escape_drawtext_path, _find_font_file
from apps.members.models import Member, UserGroup
from apps.third_party.models import ThirdPartyConnection
from base.base_test_classes import BaseAPITestCase


def _overlay_upload(name="overlay.png", size=(200, 300)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle(
        [0, 0, size[0] - 1, size[1] - 1], outline=(255, 0, 128, 255), width=10,
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


def _background_upload(name="bg.png", size=(200, 300), color=(10, 200, 10)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


def _photo_upload(name="photo.png", size=(400, 600), color=(30, 130, 220)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


def _probe_size(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path),
        ],
        capture_output=True, check=True,
    )
    width, height = result.stdout.decode().strip().splitlines()[0].split("x")
    return int(width), int(height)


def _sample_pixel(path, x, y):
    with Image.open(path) as img:
        img = img.convert("RGB")
        return img.getpixel((x, y))


class PostDeskBaseTest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.member = Member.objects.create(user=self.user, full_name="Koc One")
        self.authenticate()

    def create_postdesk_frame(self, **extra):
        data = {
            "name": "PostDesk Frame",
            "frame_type": 2,
            "background": _background_upload(),
            "image": _overlay_upload(),
            "members": [str(self.member.uuid)],
        }
        data.update(extra)
        data = {key: value for key, value in data.items() if value is not None}
        from apps.crmadmin.models import Admin
        from base.models import UserModel

        admin_user = UserModel.objects.filter(username="pd_admin").first()
        if admin_user is None:
            admin_user = UserModel.objects.create(username="pd_admin")
            Admin.objects.create(user=admin_user, full_name="PD Admin")

        old_creds = self.client._credentials.copy()
        self.authenticate(admin_user)
        response = self.client.post("/frame/library/", data=data, format="multipart")
        self.client._credentials = old_creds
        return response


class SourceVideoUploadTest(PostDeskBaseTest):
    def test_upload_creates_source_video_ready_immediately(self):
        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload()},
            format="multipart",
        )
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["pull_status"] == 2
        assert data["media_type"] == 2
        assert data["original_name"] == "photo.png"
        assert data["original_file"].startswith("http://testserver/media/")

        source_video = models.SourceVideo.objects.get(uuid=data["uuid"])
        assert source_video.member_id == self.member.id
        assert source_video.pull_failure_reason == ""

    def test_upload_requires_authentication(self):
        self.client.credentials()
        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload()},
            format="multipart",
        )
        assert response.status_code == 401

    def test_upload_requires_file(self):
        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={},
            format="multipart",
        )
        assert response.status_code == 400
        assert "details" in response.json()

    def test_list_shows_uploaded_videos_for_this_member_only(self):
        other_user_member = Member.objects.create(
            user=self.user.__class__.objects.create(username="other_koc"),
            full_name="Other Koc",
        )
        models.SourceVideo.objects.create(
            member=other_user_member,
            original_file=_photo_upload(),
            media_type=2,
            original_name="not-mine.png",
            pull_status=2,
        )
        self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload(name="mine.png")},
            format="multipart",
        )

        response = self.client.get(f"/members/{self.member.uuid}/source-video/")
        assert response.status_code == 200
        names = [row["original_name"] for row in response.json()["results"]]
        assert names == ["mine.png"]

    def test_detail_endpoint_returns_single_source_video(self):
        created = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload()},
            format="multipart",
        ).json()

        response = self.client.get(
            f"/members/{self.member.uuid}/source-video/{created['uuid']}/"
        )
        assert response.status_code == 200
        assert response.json()["uuid"] == created["uuid"]

    def test_pagination_is_applied_to_source_video_list(self):
        for i in range(3):
            self.client.post(
                f"/members/{self.member.uuid}/source-video/upload/",
                data={"file": _photo_upload(name=f"p{i}.png")},
                format="multipart",
            )
        response = self.client.get(
            f"/members/{self.member.uuid}/source-video/", data={"page_size": 2},
        )
        body = response.json()
        assert "results" in body and "count" in body
        assert len(body["results"]) == 2
        assert body["count"] == 3


class SourceVideoPullTest(PostDeskBaseTest):
    def test_pull_without_connection_fails_cleanly(self):
        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/pull/",
            data={
                "connection_uuid": "00000000-0000-0000-0000-000000000000",
                "source_url": "https://example.com/post/123",
            },
            format="json",
        )
        assert response.status_code == 400, response.content
        body = response.json()
        assert "error" in body and "details" in body
        assert models.SourceVideo.objects.count() == 0

    def test_pull_with_expired_connection_is_rejected(self):
        connection = ThirdPartyConnection.objects.create(
            member=self.member,
            provider=1,
            account_id="acct-1",
            access_token_encrypted="x",
            token_expires_at=timezone.now() - timezone.timedelta(hours=1),
        )
        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/pull/",
            data={
                "connection_uuid": str(connection.uuid),
                "source_url": "https://example.com/post/123",
            },
            format="json",
        )
        assert response.status_code == 400, response.content
        assert "expired" in response.json()["error"].lower()
        assert models.SourceVideo.objects.count() == 0

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_pull_task_marks_failed_when_connection_missing_at_task_time(self):
        from apps.frames.tasks import pull_source_video

        connection = ThirdPartyConnection.objects.create(
            member=self.member,
            provider=1,
            account_id="acct-1",
            access_token_encrypted="x",
        )
        source_video = models.SourceVideo.objects.create(
            member=self.member,
            connection=connection,
            source_url="https://example.com/post/123",
            pull_status=1,
        )
        connection.archived = timezone.now()
        connection.token_expires_at = timezone.now() - timezone.timedelta(hours=1)
        connection.save()

        pull_source_video(source_video.id)

        source_video.refresh_from_db()
        assert source_video.pull_status == 3
        assert "expired" in source_video.pull_failure_reason.lower()

    def test_pull_missing_fields_returns_400(self):
        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/pull/",
            data={},
            format="json",
        )
        assert response.status_code == 400


class MemberPostDeskFrameViewSetTest(PostDeskBaseTest):
    def test_lists_only_frame_type_2_assigned_directly(self):
        frame = self.create_postdesk_frame(name="Direct Frame").json()
        response = self.client.get(f"/members/{self.member.uuid}/postdesk-frames/")
        assert response.status_code == 200
        names = [f["name"] for f in response.json()["results"]]
        assert names == ["Direct Frame"]
        assert response.json()["results"][0]["uuid"] == frame["uuid"]

    def test_lists_frame_assigned_via_group(self):
        group = UserGroup.objects.create(name="Grp")
        group.members.add(self.member)
        self.create_postdesk_frame(name="Group Frame", members=[], user_groups=[str(group.uuid)])

        response = self.client.get(f"/members/{self.member.uuid}/postdesk-frames/")
        names = [f["name"] for f in response.json()["results"]]
        assert names == ["Group Frame"]

    def test_excludes_frames_not_assigned_to_this_member(self):
        other_user = self.user.__class__.objects.create(username="unassigned_koc")
        other_member = Member.objects.create(user=other_user, full_name="Unassigned")
        self.create_postdesk_frame(name="Someone Elses Frame", members=[str(other_member.uuid)])

        response = self.client.get(f"/members/{self.member.uuid}/postdesk-frames/")
        assert response.json()["results"] == []

    def test_excludes_job_frames_even_if_somehow_assigned(self):
        from apps.jobs.models import Company, Job, MemberJob

        company = Company.objects.create(name="Acme")
        job = Job.objects.create(company=company, title="J", start_date=timezone.now())
        MemberJob.objects.create(member=self.member, job=job, status=2)
        job_frame = models.Frame.objects.create(name="Job Frame", frame_type=1, image=_overlay_upload())
        models.FrameAssignment.objects.create(frame=job_frame, job=job)

        response = self.client.get(f"/members/{self.member.uuid}/postdesk-frames/")
        assert response.json()["results"] == []

    def test_excludes_archived_frame(self):
        frame_data = self.create_postdesk_frame(name="Archived Frame").json()
        frame = models.Frame.objects.get(uuid=frame_data["uuid"])
        frame.archive()

        response = self.client.get(f"/members/{self.member.uuid}/postdesk-frames/")
        assert response.json()["results"] == []

    def test_excludes_inactive_status_frame(self):
        frame_data = self.create_postdesk_frame(name="Inactive Frame", status=2).json()
        response = self.client.get(f"/members/{self.member.uuid}/postdesk-frames/")
        assert response.json()["results"] == []

    def test_requires_authentication(self):
        self.client.credentials()
        response = self.client.get(f"/members/{self.member.uuid}/postdesk-frames/")
        assert response.status_code == 401

    def test_admin_user_without_member_gets_empty_list_not_error(self):
        from apps.crmadmin.models import Admin
        from base.models import UserModel

        admin_user = UserModel.objects.create(username="viewer_admin")
        Admin.objects.create(user=admin_user, full_name="Viewer Admin")
        self.create_postdesk_frame(name="Some Frame")

        self.authenticate(admin_user)
        response = self.client.get(f"/members/{self.member.uuid}/postdesk-frames/")
        assert response.status_code == 200
        assert response.json()["results"] == []


class PostDeskRenderCreateTest(PostDeskBaseTest):
    def upload_source_video(self, **kwargs):
        upload = kwargs.pop("upload", None) or _photo_upload()
        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": upload},
            format="multipart",
        )
        assert response.status_code == 201, response.content
        return response.json()["uuid"]

    def render_url(self, source_video_uuid):
        return f"/members/{self.member.uuid}/source-video/{source_video_uuid}/render/"

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_with_background_only(self):
        frame = self.create_postdesk_frame(image=None).json()
        source_video_uuid = self.upload_source_video()

        response = self.client.post(
            self.render_url(source_video_uuid),
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2
        assert rendered.rendered_file

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_with_overlay_only(self):
        frame = self.create_postdesk_frame(background=None).json()
        source_video_uuid = self.upload_source_video()

        response = self.client.post(
            self.render_url(source_video_uuid),
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2
        assert rendered.rendered_file

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_with_both_layers(self):
        frame = self.create_postdesk_frame().json()
        source_video_uuid = self.upload_source_video()

        response = self.client.post(
            self.render_url(source_video_uuid),
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2
        assert rendered.rendered_file

    def test_frame_with_neither_layer_is_rejected_at_creation(self):
        response = self.create_postdesk_frame(background=None, image=None)
        assert response.status_code == 400
        assert models.Frame.objects.filter(frame_type=2).count() == 0

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_with_caption_fields(self):
        frame = self.create_postdesk_frame().json()
        source_video_uuid = self.upload_source_video()

        response = self.client.post(
            self.render_url(source_video_uuid),
            data={
                "frame_uuid": frame["uuid"],
                "caption_text": "Hello World",
                "caption_color": "yellow",
                "caption_background_color": "black",
                "caption_font_size": 32,
                "caption_x": 10,
                "caption_y": 20,
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["caption_text"] == "Hello World"
        assert data["caption_font_size"] == 32

        rendered = models.RenderedContent.objects.get(uuid=data["uuid"])
        assert rendered.render_status == 2
        assert rendered.rendered_file

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_without_caption_fields_defaults_blank(self):
        frame = self.create_postdesk_frame().json()
        source_video_uuid = self.upload_source_video()

        response = self.client.post(
            self.render_url(source_video_uuid),
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["caption_text"] == ""
        assert data["caption_font_size"] is None

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_with_crop(self):
        frame = self.create_postdesk_frame().json()
        source_video_uuid = self.upload_source_video()

        response = self.client.post(
            self.render_url(source_video_uuid),
            data={
                "frame_uuid": frame["uuid"],
                "crop_x": 50, "crop_y": 50, "crop_width": 200, "crop_height": 300,
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2
        assert rendered.crop_width == 200

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_without_crop_uses_full_source(self):
        frame = self.create_postdesk_frame().json()
        source_video_uuid = self.upload_source_video()

        response = self.client.post(
            self.render_url(source_video_uuid),
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["crop_x"] is None
        assert data["crop_width"] is None

    def test_render_rejects_frame_not_ready_source_video(self):
        frame = self.create_postdesk_frame().json()
        source_video = models.SourceVideo.objects.create(
            member=self.member, pull_status=1,
        )
        response = self.client.post(
            self.render_url(str(source_video.uuid)),
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 400, response.content
        assert "isn't ready" in response.json()["error"].lower()

    def test_render_unknown_frame_is_rejected(self):
        source_video_uuid = self.upload_source_video()
        response = self.client.post(
            self.render_url(source_video_uuid),
            data={"frame_uuid": "00000000-0000-0000-0000-000000000000"},
            format="json",
        )
        assert response.status_code == 400

    def test_render_unknown_source_video_is_rejected(self):
        frame = self.create_postdesk_frame().json()
        response = self.client.post(
            self.render_url("00000000-0000-0000-0000-000000000000"),
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 400

    def test_render_wrong_member_uuid_in_url_is_rejected(self):
        other_user = self.user.__class__.objects.create(username="mismatched")
        Member.objects.create(user=other_user, full_name="Mismatched")
        frame = self.create_postdesk_frame().json()
        source_video_uuid = self.upload_source_video()

        response = self.client.post(
            f"/members/{'0'*8}-0000-0000-0000-{'0'*12}/source-video/{source_video_uuid}/render/",
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 400


class DownloadedActionAndExpiryTest(PostDeskBaseTest):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_downloaded_deletes_file_but_keeps_row(self):
        frame = self.create_postdesk_frame().json()
        source_video = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload()},
            format="multipart",
        ).json()

        rendered = self.client.post(
            f"/members/{self.member.uuid}/source-video/{source_video['uuid']}/render/",
            data={"frame_uuid": frame["uuid"]},
            format="json",
        ).json()

        downloaded = self.client.post(
            f"/members/{self.member.uuid}/source-video/{source_video['uuid']}"
            f"/render/{rendered['uuid']}/downloaded/"
        )
        assert downloaded.status_code == 200, downloaded.content
        assert downloaded.json()["rendered_file"] is None

        row = models.RenderedContent.objects.get(uuid=rendered["uuid"])
        assert not row.rendered_file

    def test_frame_type_1_render_does_not_schedule_expiry(self):
        from apps.jobs.models import Company, Job, MemberJob

        company = Company.objects.create(name="Acme")
        job = Job.objects.create(company=company, title="J", start_date=timezone.now())
        MemberJob.objects.create(member=self.member, job=job, status=2)
        job_frame = models.Frame.objects.create(name="Job Frame", frame_type=1, image=_overlay_upload())
        models.FrameAssignment.objects.create(frame=job_frame, job=job)

        source_video = models.SourceVideo.objects.create(
            member=self.member, original_file=_photo_upload(), media_type=2,
            original_name="p.png", pull_status=2,
        )
        rendered = models.RenderedContent.objects.create(
            source_video=source_video, frame=job_frame, member=self.member,
        )

        with patch("apps.frames.tasks.expire_rendered_file.apply_async") as mock_apply_async:
            from apps.frames.tasks import render_content
            render_content(rendered.id)

        mock_apply_async.assert_not_called()
        rendered.refresh_from_db()
        assert rendered.render_status == 2

    def test_frame_type_2_render_schedules_expiry_with_24h_countdown(self):
        frame = models.Frame.objects.create(
            name="PD Frame", frame_type=2, background=_background_upload(),
        )
        models.FrameAssignment.objects.create(frame=frame, member=self.member)

        source_video = models.SourceVideo.objects.create(
            member=self.member, original_file=_photo_upload(), media_type=2,
            original_name="p.png", pull_status=2,
        )
        rendered = models.RenderedContent.objects.create(
            source_video=source_video, frame=frame, member=self.member,
        )

        with patch("apps.frames.tasks.expire_rendered_file.apply_async") as mock_apply_async:
            from apps.frames.tasks import render_content
            render_content(rendered.id)

        mock_apply_async.assert_called_once()
        _, kwargs = mock_apply_async.call_args
        assert kwargs["args"] == [rendered.id]
        assert kwargs["countdown"] == 24 * 60 * 60

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_expire_task_is_a_noop_before_24h_elapsed(self):
        frame = models.Frame.objects.create(
            name="PD Frame", frame_type=2, background=_background_upload(),
        )
        models.FrameAssignment.objects.create(frame=frame, member=self.member)
        source_video = models.SourceVideo.objects.create(
            member=self.member, original_file=_photo_upload(), media_type=2,
            original_name="p.png", pull_status=2,
        )
        rendered = models.RenderedContent.objects.create(
            source_video=source_video, frame=frame, member=self.member,
        )
        from apps.frames.tasks import render_content
        render_content(rendered.id)

        rendered.refresh_from_db()
        assert rendered.render_status == 2
        assert rendered.rendered_file

    def test_expire_task_deletes_file_once_actually_old(self):
        frame = models.Frame.objects.create(
            name="PD Frame", frame_type=2, background=_background_upload(),
        )
        source_video = models.SourceVideo.objects.create(
            member=self.member, original_file=_photo_upload(), media_type=2,
            original_name="p.png", pull_status=2,
        )
        rendered = models.RenderedContent.objects.create(
            source_video=source_video, frame=frame, member=self.member,
            render_status=2, rendered_file=_photo_upload(name="out.png"),
        )
        old_time = timezone.now() - timezone.timedelta(hours=25)
        models.RenderedContent.objects.filter(id=rendered.id).update(modified=old_time)

        from apps.frames.tasks import expire_rendered_file
        expire_rendered_file(rendered.id)

        rendered.refresh_from_db()
        assert not rendered.rendered_file


class CaptionFilterTest(BaseAPITestCase):
    """Unit coverage for _caption_filter / _escape_drawtext_path (tasks.py).

    _caption_filter writes caption text to a file under tmp_dir and returns
    a textfile= drawtext filter (see tasks.py's docstring for why: inline
    text='...' can't represent an apostrophe, and '%' needs expansion=none).
    Every call here needs a real tmp_dir and a font file on the box, or the
    function short-circuits to None by design - tests that need a filter
    skip cleanly instead of failing when no font is installed.
    """

    def setUp(self):
        super().setUp()
        if _find_font_file() is None:
            self.skipTest("No usable font file found on this machine for drawtext")

    def test_blank_caption_text_produces_no_filter(self):
        rendered = models.RenderedContent(caption_text="")
        with tempfile.TemporaryDirectory() as tmp_dir:
            assert _caption_filter(rendered, (200, 300), tmp_dir) is None

    def test_basic_caption_produces_drawtext_filter(self):
        rendered = models.RenderedContent(caption_text="Hello", caption_color="white")
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _caption_filter(rendered, (200, 300), tmp_dir)
            assert result.startswith("drawtext=")
            assert "textfile=" in result
            assert "fontcolor=white" in result
            assert "expansion=none" in result

            text_path = Path(tmp_dir).glob("caption_*.txt")
            content = next(text_path).read_text(encoding="utf-8")
            assert content == "Hello"

    def test_font_size_defaults_from_canvas_height(self):
        rendered = models.RenderedContent(caption_text="Hi")
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _caption_filter(rendered, (200, 400), tmp_dir)
            assert "fontsize=20" in result

    def test_explicit_font_size_is_used(self):
        rendered = models.RenderedContent(caption_text="Hi", caption_font_size=40)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _caption_filter(rendered, (200, 400), tmp_dir)
            assert "fontsize=40" in result

    def test_explicit_position_is_resolved_as_canvas_percentage(self):
        rendered = models.RenderedContent(caption_text="Hi", caption_x=15, caption_y=25)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _caption_filter(rendered, (200, 400), tmp_dir)
            assert "x=(w*0.150000)-(text_w/2)" in result
            assert "y=(h*0.250000)-(text_h/2)" in result

    def test_position_percentage_is_canvas_size_independent(self):
        rendered = models.RenderedContent(caption_text="Hi", caption_x=50, caption_y=88)
        with tempfile.TemporaryDirectory() as tmp_dir:
            small = _caption_filter(rendered, (200, 400), tmp_dir)
            large = _caption_filter(rendered, (1080, 1920), tmp_dir)
        for result in (small, large):
            assert "x=(w*0.500000)-(text_w/2)" in result
            assert "y=(h*0.880000)-(text_h/2)" in result

    def test_font_size_scales_to_canvas_from_reference_height(self):
        rendered = models.RenderedContent(
            caption_text="Hi", caption_font_size=18, caption_reference_height=480,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _caption_filter(rendered, (1080, 1920), tmp_dir)
        assert "fontsize=72" in result

    def test_font_size_unscaled_without_reference_height(self):
        rendered = models.RenderedContent(caption_text="Hi", caption_font_size=40)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _caption_filter(rendered, (1080, 1920), tmp_dir)
        assert "fontsize=40" in result

    def test_background_color_adds_box(self):
        rendered = models.RenderedContent(caption_text="Hi", caption_background_color="black")
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _caption_filter(rendered, (200, 400), tmp_dir)
            assert "box=1" in result
            assert "boxcolor=black@0.75" in result

    def test_no_background_color_omits_box(self):
        rendered = models.RenderedContent(caption_text="Hi")
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _caption_filter(rendered, (200, 400), tmp_dir)
            assert "box=1" not in result

    def test_escape_drawtext_path_handles_special_characters(self):
        raw = r"C:/tmp/it's:weird.ttf"
        escaped = _escape_drawtext_path(raw)
        assert escaped == r"C\:/tmp/it\'s\:weird.ttf"

    def test_escape_drawtext_path_handles_backslash_itself(self):
        assert _escape_drawtext_path("a\\b") == "a\\\\b"

    def test_caption_with_colons_quotes_percent_does_not_crash_ffmpeg(self):
        rendered = models.RenderedContent(
            caption_text="""50%: it's "huge"!""", caption_color="white",
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            filter_str = _caption_filter(rendered, (200, 300), tmp_dir)
            out_path = Path(tmp_dir) / "out.png"
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=200x300",
                "-frames:v", "1",
                "-vf", filter_str,
                str(out_path),
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            assert result.returncode == 0, result.stderr.decode(errors="replace")
            assert out_path.exists()


class LayerCompositionRenderTest(PostDeskBaseTest):
    """Pixel-level verification of the composition order:

        background -> content -> overlay -> caption

    The content fills the whole canvas (it is never inset), the overlay is
    composited last at full canvas size so its artwork is never shrunk and
    its transparent regions reveal the content beneath, and the background
    shows through wherever the content does not reach.
    """

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_content_fills_canvas_over_background(self):
        bg_color = (10, 200, 10)
        content_color = (30, 130, 220)
        frame = self.create_postdesk_frame(
            image=None,
            background=_background_upload(color=bg_color, size=(200, 300)),
        ).json()
        source_video_uuid = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload(color=content_color, size=(400, 600))},
            format="multipart",
        ).json()["uuid"]

        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/{source_video_uuid}/render/",
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2

        path = rendered.rendered_file.path
        width, height = _probe_size(path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_png = Path(tmp_dir) / "frame.png"
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-frames:v", "1", str(frame_png)],
                capture_output=True, check=True,
            )
            corner = _sample_pixel(frame_png, 2, 2)
            center = _sample_pixel(frame_png, width // 2, height // 2)

        def _closer_to(pixel, a, b):
            dist_a = sum((p - c) ** 2 for p, c in zip(pixel, a))
            dist_b = sum((p - c) ** 2 for p, c in zip(pixel, b))
            return dist_a < dist_b

        assert _closer_to(corner, content_color, bg_color), corner
        assert _closer_to(center, content_color, bg_color), center

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_overlay_composites_above_background(self):
        bg_color = (10, 200, 10)
        content_color = (30, 130, 220)
        frame = self.create_postdesk_frame(
            image=_overlay_upload(size=(200, 300)),
            background=_background_upload(color=bg_color, size=(200, 300)),
        ).json()
        source_video_uuid = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload(color=content_color, size=(400, 600))},
            format="multipart",
        ).json()["uuid"]

        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/{source_video_uuid}/render/",
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2

        path = rendered.rendered_file.path
        width, height = _probe_size(path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_png = Path(tmp_dir) / "frame.png"
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-frames:v", "1", str(frame_png)],
                capture_output=True, check=True,
            )
            edge = _sample_pixel(frame_png, 2, height // 2)
            center = _sample_pixel(frame_png, width // 2, height // 2)

        assert edge[0] > 150 and edge[2] > 60, edge
        assert abs(center[2] - content_color[2]) < 60, center

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_zoomed_out_crop_reveals_background_not_black(self):
        bg_color = (10, 200, 10)
        content_color = (30, 130, 220)
        frame = self.create_postdesk_frame(
            image=None,
            background=_background_upload(color=bg_color, size=(200, 300)),
        ).json()
        source_video_uuid = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload(color=content_color, size=(400, 600))},
            format="multipart",
        ).json()["uuid"]

        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/{source_video_uuid}/render/",
            data={
                "frame_uuid": frame["uuid"],
                "crop_x": -100, "crop_y": -150,
                "crop_width": 600, "crop_height": 900,
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2

        path = rendered.rendered_file.path
        width, height = _probe_size(path)

        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_png = Path(tmp_dir) / "frame.png"
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-frames:v", "1", str(frame_png)],
                capture_output=True, check=True,
            )
            margin = _sample_pixel(frame_png, 2, height // 2)
            center = _sample_pixel(frame_png, width // 2, height // 2)

        assert margin[1] > margin[0] and margin[1] > margin[2], margin
        assert abs(center[2] - content_color[2]) < 60, center

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_no_background_content_fills_full_canvas(self):
        content_color = (30, 130, 220)
        frame = self.create_postdesk_frame(background=None).json()
        source_video_uuid = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload(color=content_color, size=(400, 600))},
            format="multipart",
        ).json()["uuid"]

        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/{source_video_uuid}/render/",
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2

        path = rendered.rendered_file.path

        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_png = Path(tmp_dir) / "frame.png"
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-frames:v", "1", str(frame_png)],
                capture_output=True, check=True,
            )
            inside = _sample_pixel(frame_png, 30, 30)

        assert abs(inside[2] - content_color[2]) < 40, inside


class OverlayTransformTest(BaseAPITestCase):
    def test_identity_when_untransformed(self):
        from apps.frames.tasks import _overlay_is_transformed, _overlay_transform

        rendered = models.RenderedContent()
        assert _overlay_is_transformed(rendered) is False

        (w, h), (x, y) = _overlay_transform(rendered, (200, 300))
        assert (w, h) == (200, 300)
        assert (x, y) == (0, 0)

    def test_zoom_scales_from_the_centre(self):
        from apps.frames.tasks import _overlay_transform

        rendered = models.RenderedContent(overlay_zoom=0.5)
        (w, h), (x, y) = _overlay_transform(rendered, (200, 300))
        assert (w, h) == (100, 150)
        assert (x, y) == (50, 75)

    def test_offset_is_a_canvas_percentage(self):
        from apps.frames.tasks import _overlay_transform

        rendered = models.RenderedContent(overlay_x=25, overlay_y=10)
        (w, h), (x, y) = _overlay_transform(rendered, (200, 300))
        assert (w, h) == (200, 300)
        assert (x, y) == (50, 30)

    def test_dimensions_stay_even(self):
        from apps.frames.tasks import _overlay_transform

        rendered = models.RenderedContent(overlay_zoom=0.337)
        (w, h), _ = _overlay_transform(rendered, (201, 301))
        assert w % 2 == 0
        assert h % 2 == 0

    def test_zero_or_missing_zoom_falls_back_to_identity_scale(self):
        from apps.frames.tasks import _overlay_transform

        for zoom in (None, 0):
            rendered = models.RenderedContent(overlay_zoom=zoom)
            (w, h), _ = _overlay_transform(rendered, (200, 300))
            assert (w, h) == (200, 300)


class OverlayTransformRenderTest(PostDeskBaseTest):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_zoomed_out_overlay_shrinks_toward_the_centre(self):
        content_color = (30, 130, 220)
        frame = self.create_postdesk_frame(
            image=_overlay_upload(size=(200, 300)),
            background=_background_upload(color=(10, 200, 10), size=(200, 300)),
        ).json()
        source_video_uuid = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload(color=content_color, size=(400, 600))},
            format="multipart",
        ).json()["uuid"]

        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/{source_video_uuid}/render/",
            data={"frame_uuid": frame["uuid"], "overlay_zoom": 0.5},
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2

        path = rendered.rendered_file.path
        width, height = _probe_size(path)
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_png = Path(tmp_dir) / "frame.png"
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-frames:v", "1", str(frame_png)],
                capture_output=True, check=True,
            )
            edge = _sample_pixel(frame_png, 2, height // 2)

        assert not (edge[0] > 150 and edge[2] > 60), (
            "overlay border must have moved inward at 0.5x zoom", edge,
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_untransformed_overlay_still_spans_the_canvas(self):
        frame = self.create_postdesk_frame(
            image=_overlay_upload(size=(200, 300)),
            background=_background_upload(color=(10, 200, 10), size=(200, 300)),
        ).json()
        source_video_uuid = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload(color=(30, 130, 220), size=(400, 600))},
            format="multipart",
        ).json()["uuid"]

        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/{source_video_uuid}/render/",
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2

        path = rendered.rendered_file.path
        width, height = _probe_size(path)
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_png = Path(tmp_dir) / "frame.png"
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-frames:v", "1", str(frame_png)],
                capture_output=True, check=True,
            )
            edge = _sample_pixel(frame_png, 2, height // 2)

        assert edge[0] > 150 and edge[2] > 60, edge


class CanvasSizeTest(PostDeskBaseTest):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_background_defines_the_canvas_not_the_overlay(self):
        # The background is the canvas. A differently shaped overlay must be
        # scaled onto it, never the other way round.
        frame = self.create_postdesk_frame(
            image=_overlay_upload(size=(500, 500)),
            background=_background_upload(color=(10, 200, 10), size=(200, 400)),
        ).json()
        source_video_uuid = self.client.post(
            f"/members/{self.member.uuid}/source-video/upload/",
            data={"file": _photo_upload(color=(30, 130, 220), size=(400, 600))},
            format="multipart",
        ).json()["uuid"]

        response = self.client.post(
            f"/members/{self.member.uuid}/source-video/{source_video_uuid}/render/",
            data={"frame_uuid": frame["uuid"]},
            format="json",
        )
        assert response.status_code == 201, response.content
        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2

        width, height = _probe_size(rendered.rendered_file.path)
        assert (width, height) == (200, 400), (
            "canvas must come from the background (200x400), not the "
            f"500x500 overlay; got {width}x{height}"
        )
