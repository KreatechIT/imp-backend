import os
import subprocess
import tempfile
from uuid import uuid4

from celery import shared_task
from django.core.files import File
from django.utils import timezone

from apps.jobs import helper_functions
from apps.notifications import helper_functions as notifications


@shared_task
def render_task_file(task_file_id):
    from apps.jobs.models import TaskFile

    original = TaskFile.objects.select_related(
        "task__member_job__member__user", "frame",
    ).filter(id=task_file_id).first()
    if original is None or original.frame is None:
        return

    task = original.task
    frame = original.frame
    is_animated_frame = frame.image.name.lower().endswith(".gif")
    is_video_content = original.media_type == 1

    composited = TaskFile.objects.create(
        task=task,
        file=original.file,
        media_type=original.media_type,
        original_name=original.original_name,
        size=0,
        frame=frame,
        is_original=False,
        render_status=1,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        content_path = os.path.join(tmp_dir, os.path.basename(original.file.name))
        with open(content_path, "wb") as fh:
            for chunk in original.file.chunks():
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
            composited.render_status = 3
            composited.save()
            return

        with open(out_path, "rb") as fh:
            composited.file.save(
                f"{uuid4().hex}{out_ext}", File(fh), save=False,
            )
        composited.media_type = 1 if out_ext == ".mp4" else 2
        composited.size = composited.file.size
        composited.render_status = 2
        composited.save()

    member_user = task.member_job.member.user
    notifications.notify(
        recipient=member_user,
        role=2,
        notification_type=6,
        title="Your framed content is ready",
        message=str(task.requirement),
    )
