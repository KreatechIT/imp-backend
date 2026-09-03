import os
import subprocess
import tempfile
from uuid import uuid4

from celery import shared_task
from django.core.files import File

from apps.notifications import helper_functions as notifications


@shared_task
def render_content(rendered_content_id):
    from apps.frames.models import RenderedContent

    rendered = RenderedContent.objects.select_related(
        "frame", "member__user",
    ).filter(id=rendered_content_id).first()
    if rendered is None:
        return

    frame = rendered.frame
    is_animated_frame = frame.image.name.lower().endswith(".gif")
    is_video_content = rendered.media_type == 1

    with tempfile.TemporaryDirectory() as tmp_dir:
        content_path = os.path.join(tmp_dir, os.path.basename(rendered.original_file.name))
        with open(content_path, "wb") as fh:
            for chunk in rendered.original_file.chunks():
                fh.write(chunk)

        frame_path = os.path.join(tmp_dir, os.path.basename(frame.image.name))
        with open(frame_path, "wb") as fh:
            for chunk in frame.image.chunks():
                fh.write(chunk)

        if is_video_content:
            out_ext = ".mp4"
        elif is_animated_frame:
            out_ext = ".gif"
        else:
            out_ext = ".jpg"
        out_path = os.path.join(tmp_dir, f"{uuid4().hex}{out_ext}")

        if is_video_content:
            cmd = [
                "ffmpeg", "-y",
                "-i", content_path,
            ]
            if is_animated_frame:
                cmd += ["-ignore_loop", "0"]
            cmd += [
                "-i", frame_path,
                "-filter_complex", "overlay=0:0:shortest=1",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                out_path,
            ]
        else:
            if is_animated_frame:
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", content_path,
                    "-i", frame_path,
                    "-filter_complex", "overlay=0:0:shortest=1",
                    out_path,
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", content_path,
                    "-i", frame_path,
                    "-filter_complex", "overlay=0:0",
                    "-frames:v", "1",
                    out_path,
                ]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0 or not os.path.exists(out_path):
            rendered.render_status = 3
            rendered.save()
            return

        with open(out_path, "rb") as fh:
            rendered.rendered_file.save(
                f"{uuid4().hex}{out_ext}", File(fh), save=False,
            )
        rendered.render_status = 2
        rendered.save()

    notifications.notify(
        recipient=rendered.member.user,
        role=2,
        notification_type=6,
        title="Your framed content is ready",
        message=frame.name,
    )
