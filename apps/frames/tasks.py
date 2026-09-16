import os
import subprocess
import tempfile
from uuid import uuid4

from celery import shared_task
from django.core.files import File

from apps.notifications import helper_functions as notifications

STRETCH_TO_FRAME = "scale2ref=w=trunc(iw/2)*2:h=trunc(ih/2)*2[content][frame]"

MAX_CANVAS_LONG_EDGE = 1920
MAX_CANVAS_SHORT_EDGE = 1080


def _capped_canvas(frame_size):
    frame_width, frame_height = frame_size
    if frame_width >= frame_height:
        max_width, max_height = MAX_CANVAS_LONG_EDGE, MAX_CANVAS_SHORT_EDGE
    else:
        max_width, max_height = MAX_CANVAS_SHORT_EDGE, MAX_CANVAS_LONG_EDGE

    scale = min(1.0, max_width / frame_width, max_height / frame_height)
    if scale >= 1.0:
        return None
    return (
        max(2, int(frame_width * scale) // 2 * 2),
        max(2, int(frame_height * scale) // 2 * 2),
    )


def _probe_size(path):
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0:s=x",
                path,
            ],
            capture_output=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        width, height = result.stdout.decode().strip().splitlines()[0].split("x")
        return int(width), int(height)
    except (ValueError, IndexError):
        return None


def _visible_part(rect, source_size):
    x, y, width, height = rect
    source_width, source_height = source_size
    left, top = max(x, 0), max(y, 0)
    right, bottom = min(x + width, source_width), min(y + height, source_height)
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


def _content_graph(rendered, content_path, frame_path):
    frame_size = _probe_size(frame_path)
    canvas = _capped_canvas(frame_size) if frame_size else None

    def stretch(filters):
        if canvas:
            chain = ",".join([*filters, f"scale={canvas[0]}:{canvas[1]}"])
            return (
                f"[0:v]{chain}[content];"
                f"[1:v]scale={canvas[0]}:{canvas[1]}[frame]"
            )
        if filters:
            return f"[0:v]{','.join(filters)}[cut];[cut][1:v]{STRETCH_TO_FRAME}"
        return f"[0:v][1:v]{STRETCH_TO_FRAME}"

    has_crop = all(
        v is not None for v in (
            rendered.crop_x, rendered.crop_y,
            rendered.crop_width, rendered.crop_height,
        )
    )
    if not has_crop:
        return stretch([])

    rect = (
        rendered.crop_x, rendered.crop_y,
        rendered.crop_width, rendered.crop_height,
    )
    source_size = _probe_size(content_path)
    visible = _visible_part(rect, source_size) if source_size else None
    if visible is None:
        return stretch([])

    left, top, visible_width, visible_height = visible
    cut = f"crop={visible_width}:{visible_height}:{left}:{top}"

    if visible == rect or frame_size is None:
        return stretch([cut])

    x, y, width, height = rect
    canvas_width, canvas_height = canvas or (
        frame_size[0] // 2 * 2, frame_size[1] // 2 * 2,
    )

    inner_width = max(1, min(canvas_width, round(canvas_width * visible_width / width)))
    inner_height = max(1, min(canvas_height, round(canvas_height * visible_height / height)))
    offset_x = min(max(0, round(canvas_width * (left - x) / width)), canvas_width - inner_width)
    offset_y = min(max(0, round(canvas_height * (top - y) / height)), canvas_height - inner_height)

    frame_fit = (
        f"scale={canvas_width}:{canvas_height}" if canvas else "null"
    )
    return (
        f"[0:v]{cut},scale={inner_width}:{inner_height},"
        f"pad={canvas_width}:{canvas_height}:{offset_x}:{offset_y}:color=black"
        f"[content];[1:v]{frame_fit}[frame]"
    )


@shared_task
def render_content(rendered_content_id):
    from apps.frames.models import RenderedContent

    rendered = RenderedContent.objects.select_related(
        "frame", "member__user",
    ).filter(id=rendered_content_id).first()
    if rendered is None:
        return

    frame = rendered.frame
    if not frame.image:
        rendered.render_status = 3
        rendered.save()
        return

    is_animated_frame = frame.image.name.lower().endswith(".gif")
    is_video_content = rendered.media_type == 1

    has_trim = (
        is_video_content
        and rendered.trim_in is not None
        and rendered.trim_out is not None
        and rendered.trim_out > rendered.trim_in
    )

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

        scale_to_frame = _content_graph(rendered, content_path, frame_path)

        if is_video_content:
            cmd = ["ffmpeg", "-y"]
            if has_trim:
                cmd += ["-ss", str(rendered.trim_in), "-t", str(rendered.trim_out - rendered.trim_in)]
            cmd += ["-i", content_path]
            if is_animated_frame:
                cmd += ["-ignore_loop", "0"]
            else:
                cmd += ["-loop", "1"]
            cmd += [
                "-i", frame_path,
                "-filter_complex",
                f"{scale_to_frame};[content][frame]overlay=0:0:shortest=1",
                "-c:v", "libx264", "-preset", "medium", "-crf", "26",
                "-pix_fmt", "yuv420p",
                out_path,
            ]
        else:
            if is_animated_frame:
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", content_path,
                    "-i", frame_path,
                    "-filter_complex",
                    f"{scale_to_frame};[content][frame]overlay=0:0:shortest=1[merged];"
                    "[merged]fps=8,scale=480:-1:flags=lanczos,split[a][b];"
                    "[a]palettegen=stats_mode=diff[pal];"
                    "[b][pal]paletteuse=dither=bayer",
                    out_path,
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", content_path,
                    "-i", frame_path,
                    "-filter_complex",
                    f"{scale_to_frame};[content][frame]overlay=0:0",
                    "-frames:v", "1",
                    "-q:v", "3",
                    out_path,
                ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
        except subprocess.TimeoutExpired:
            rendered.render_status = 3
            rendered.save()
            return

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
