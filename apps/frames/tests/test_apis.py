import io
import subprocess
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.frames import models
from apps.jobs.models import Company, Job
from apps.members.models import Member
from base.base_test_classes import BaseAPITestCase


def _image_upload(name, mode, size, color):
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


def _video_upload(name="clip.mp4", duration=6):
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / name
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"testsrc=size=640x360:duration={duration}:rate=15",
                "-pix_fmt", "yuv420p", str(out_path),
            ],
            check=True, capture_output=True,
        )
        return SimpleUploadedFile(name, out_path.read_bytes(), content_type="video/mp4")


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


def _probe_duration(file_field):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_field.path,
        ],
        capture_output=True, check=True,
    )
    return float(result.stdout.decode().strip())


def _animated_frame_upload():
    frames = []
    for offset in (0, 40):
        img = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, offset, 199, 299], outline=(255, 0, 128, 255), width=15)
        frames.append(img)
    buf = io.BytesIO()
    frames[0].save(
        buf, format="GIF", save_all=True, append_images=frames[1:],
        duration=120, loop=0, disposal=2,
    )
    buf.seek(0)
    return SimpleUploadedFile("frame.gif", buf.read(), content_type="image/gif")


def _frame_upload():
    img = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 199, 299], outline=(255, 0, 128, 255), width=15)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile("frame.png", buf.read(), content_type="image/png")


class FrameRenderAPITest(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.member = Member.objects.create(user=self.user)
        company = Company.objects.create(name="Acme")
        job = Job.objects.create(company=company, title="Job", start_date=timezone.now())
        self.frame = models.Frame.objects.create(
            job=job,
            name="Test Frame",
            image=_frame_upload(),
        )
        self.url = f"/frame/{self.frame.uuid}/render/"

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_photo_with_crop(self):
        self.authenticate()
        response = self.client.post(
            self.url,
            data={
                "file": _image_upload("photo.png", "RGB", (800, 600), (30, 130, 220)),
                "crop_x": 100, "crop_y": 50, "crop_width": 500, "crop_height": 400,
            },
            format="multipart",
        )
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["crop_x"] == 100
        assert data["crop_width"] == 500

        rendered = models.RenderedContent.objects.get(uuid=data["uuid"])
        assert rendered.render_status == 2
        assert rendered.rendered_file

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_video_with_crop_and_trim(self):
        self.authenticate()
        response = self.client.post(
            self.url,
            data={
                "file": _video_upload(),
                "crop_x": 40, "crop_y": 0, "crop_width": 560, "crop_height": 360,
                "trim_in": 1, "trim_out": 3.5,
            },
            format="multipart",
        )
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["trim_in"] == 1
        assert data["trim_out"] == 3.5

        rendered = models.RenderedContent.objects.get(uuid=data["uuid"])
        assert rendered.render_status == 2, rendered.rendered_file
        assert rendered.rendered_file
        assert abs(_probe_duration(rendered.rendered_file) - 2.5) < 0.2

    def test_render_requires_authentication(self):
        response = self.client.post(self.url, data={}, format="multipart")
        assert response.status_code == 401

    def test_render_missing_frame(self):
        self.authenticate()
        response = self.client.post(
            "/frame/00000000-0000-0000-0000-000000000000/render/",
            data={"file": _image_upload("photo.png", "RGB", (10, 10), (0, 0, 0))},
            format="multipart",
        )
        assert response.status_code == 400, response.content
        assert "Frame Id" in response.json()["details"]

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_crop_reaching_past_the_source_is_padded(self):
        # What zooming out past "fills the window" produces: the framing
        # starts before the asset and ends after it, so the overhang is
        # margin. It must render as the member framed it rather than
        # snapping back to the whole asset.
        self.authenticate()
        response = self.client.post(
            self.url,
            data={
                "file": _image_upload("photo.png", "RGB", (800, 600), (30, 130, 220)),
                "crop_x": -400, "crop_y": -300, "crop_width": 1600, "crop_height": 1200,
            },
            format="multipart",
        )
        assert response.status_code == 201, response.content
        data = response.json()
        assert data["crop_x"] == -400
        assert data["crop_y"] == -300

        rendered = models.RenderedContent.objects.get(uuid=data["uuid"])
        assert rendered.render_status == 2
        assert rendered.rendered_file
        # Canvas is the frame's own resolution regardless of the overhang.
        assert _probe_size(rendered.rendered_file.path) == (200, 300)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_padded_crop_onto_animated_frame(self):
        # The animated-frame branch composes a different filter chain, so
        # the padded content has to hold up there too.
        self.frame.image = _animated_frame_upload()
        self.frame.save()
        self.authenticate()
        response = self.client.post(
            self.url,
            data={
                "file": _image_upload("photo.png", "RGB", (800, 600), (30, 130, 220)),
                "crop_x": -400, "crop_y": -300, "crop_width": 1600, "crop_height": 1200,
            },
            format="multipart",
        )
        assert response.status_code == 201, response.content

        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2
        assert rendered.rendered_file.name.endswith(".gif")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_render_padded_crop_on_video(self):
        self.authenticate()
        response = self.client.post(
            self.url,
            data={
                "file": _video_upload(),
                "crop_x": -160, "crop_y": -90, "crop_width": 960, "crop_height": 540,
            },
            format="multipart",
        )
        assert response.status_code == 201, response.content

        rendered = models.RenderedContent.objects.get(uuid=response.json()["uuid"])
        assert rendered.render_status == 2
        assert _probe_size(rendered.rendered_file.path) == (200, 300)

    def test_render_crop_fields_must_be_positive(self):
        self.authenticate()
        response = self.client.post(
            self.url,
            data={
                "file": _image_upload("photo.png", "RGB", (10, 10), (0, 0, 0)),
                "crop_width": -5,
            },
            format="multipart",
        )
        assert response.status_code == 400
