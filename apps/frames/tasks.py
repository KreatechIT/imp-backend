import os
import subprocess
import tempfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from celery import shared_task
from django.core.files import File
from django.utils import timezone

from apps.notifications import helper_functions as notifications

STRETCH_TO_FRAME = "scale2ref=w=trunc(iw/2)*2:h=trunc(ih/2)*2[content][frame]"

MAX_CANVAS_LONG_EDGE = 1920
MAX_CANVAS_SHORT_EDGE = 1080

RENDER_EXPIRY_SECONDS = 24 * 60 * 60


@shared_task
def pull_source_video(source_video_id):
    from apps.frames.models import SourceVideo
    from apps.jobs.helper_functions import media_type_for
    from apps.third_party.providers.meta import MetaAPIError
    from apps.third_party.services import download_media, resolve_media

    source_video = SourceVideo.objects.select_related("connection").filter(
        id=source_video_id,
    ).first()
    if source_video is None:
        return

    connection = source_video.connection
    if connection is None or connection.is_expired:
        source_video.pull_status = 3
        source_video.pull_failure_reason = "This connection has expired — reconnect the account and try again."
        source_video.save()
        return

    try:
        media = resolve_media(connection, source_url=source_video.source_url)
    except MetaAPIError as e:
        source_video.pull_status = 3
        source_video.pull_failure_reason = str(e)
        source_video.save()
        return

    media_url = media.get("media_url")
    if not media_url:
        source_video.pull_status = 3
        source_video.pull_failure_reason = "Meta didn't return a file for this post (it may be copyright-flagged)."
        source_video.save()
        return

    try:
        response = download_media(media_url)
    except MetaAPIError as e:
        source_video.pull_status = 3
        source_video.pull_failure_reason = str(e)
        source_video.save()
        return

    buffer = BytesIO()
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        buffer.write(chunk)
    buffer.seek(0)

    is_video = media.get("media_type") in ("VIDEO", "REELS")
    filename = f"{media.get('id', uuid4().hex)}{'.mp4' if is_video else '.jpg'}"

    source_video.original_file = File(buffer, name=filename)
    source_video.media_type = media_type_for(filename)
    source_video.original_name = filename
    source_video.pull_status = 2
    source_video.pull_failure_reason = ""
    source_video.save()


@shared_task
def expire_rendered_file(rendered_content_id):
    from apps.frames.models import RenderedContent

    rendered = RenderedContent.objects.filter(
        id=rendered_content_id, render_status=2,
    ).first()
    if rendered is None or not rendered.rendered_file:
        return

    if timezone.now() - rendered.modified < timedelta(seconds=RENDER_EXPIRY_SECONDS):
        return

    rendered.rendered_file.delete(save=False)
    rendered.save()


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


def _probe_duration(path):
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        duration = float(result.stdout.decode().strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def _visible_part(rect, source_size):
    x, y, width, height = rect
    source_width, source_height = source_size
    left, top = max(x, 0), max(y, 0)
    right, bottom = min(x + width, source_width), min(y + height, source_height)
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


def _crop_to_canvas(rect, visible, canvas_width, canvas_height, pad_color="black"):
    left, top, visible_width, visible_height = visible
    x, y, width, height = rect
    cut = f"crop={visible_width}:{visible_height}:{left}:{top}"

    inner_width = max(1, min(canvas_width, round(canvas_width * visible_width / width)))
    inner_height = max(1, min(canvas_height, round(canvas_height * visible_height / height)))
    offset_x = min(max(0, round(canvas_width * (left - x) / width)), canvas_width - inner_width)
    offset_y = min(max(0, round(canvas_height * (top - y) / height)), canvas_height - inner_height)

    pad = f"pad={canvas_width}:{canvas_height}:{offset_x}:{offset_y}:color={pad_color}"
    if pad_color == "black":
        return f"{cut},scale={inner_width}:{inner_height},{pad}"
    return f"{cut},scale={inner_width}:{inner_height},format=rgba,{pad}"


def _overlay_transform(rendered, canvas_size):
    canvas_width, canvas_height = canvas_size

    zoom = rendered.overlay_zoom
    if zoom is None or zoom <= 0:
        zoom = 1.0

    scaled_width = max(2, round(canvas_width * zoom) // 2 * 2)
    scaled_height = max(2, round(canvas_height * zoom) // 2 * 2)

    offset_x = round(canvas_width * (rendered.overlay_x or 0.0) / 100)
    offset_y = round(canvas_height * (rendered.overlay_y or 0.0) / 100)

    centred_x = round((canvas_width - scaled_width) / 2) + offset_x
    centred_y = round((canvas_height - scaled_height) / 2) + offset_y

    return (scaled_width, scaled_height), (centred_x, centred_y)


def _overlay_is_transformed(rendered):
    return (
        (rendered.overlay_zoom is not None and rendered.overlay_zoom != 1.0)
        or bool(rendered.overlay_x)
        or bool(rendered.overlay_y)
    )


def _content_graph(rendered, content_path, frame_path, content_box=None, pad_color="black"):
    if content_box is not None:
        canvas = content_box
        frame_size = content_box
    else:
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

    canvas_width, canvas_height = canvas or (
        frame_size[0] // 2 * 2, frame_size[1] // 2 * 2,
    )
    frame_fit = f"scale={canvas_width}:{canvas_height}" if canvas else "null"
    return (
        f"[0:v]{_crop_to_canvas(rect, visible, canvas_width, canvas_height, pad_color)}[content];"
        f"[1:v]{frame_fit}[frame]"
    )


def _content_graph_no_overlay(rendered, content_path, canvas_size, pad_color="black"):
    canvas_width, canvas_height = canvas_size

    has_crop = all(
        v is not None for v in (
            rendered.crop_x, rendered.crop_y,
            rendered.crop_width, rendered.crop_height,
        )
    )
    if not has_crop:
        return f"[0:v]scale={canvas_width}:{canvas_height}[content]"

    rect = (
        rendered.crop_x, rendered.crop_y,
        rendered.crop_width, rendered.crop_height,
    )
    source_size = _probe_size(content_path)
    visible = _visible_part(rect, source_size) if source_size else None
    if visible is None:
        return f"[0:v]scale={canvas_width}:{canvas_height}[content]"

    if visible == rect:
        left, top, visible_width, visible_height = visible
        return f"[0:v]crop={visible_width}:{visible_height}:{left}:{top},scale={canvas_width}:{canvas_height}[content]"

    return f"[0:v]{_crop_to_canvas(rect, visible, canvas_width, canvas_height, pad_color)}[content]"


def _escape_drawtext_path(path):
    return (
        path.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )


_BUNDLED_FONT = str(Path(__file__).resolve().parent / "fonts" / "Roboto-Regular.ttf")

_FONT_CANDIDATES = (
    _BUNDLED_FONT,
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _find_font_file():
    for candidate in _FONT_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def _caption_filter(rendered, canvas_size, tmp_dir):
    if not rendered.caption_text:
        return None

    font_file = _find_font_file()
    if font_file is None:
        return None

    text_path = os.path.join(tmp_dir, f"caption_{uuid4().hex}.txt")
    with open(text_path, "w", encoding="utf-8") as fh:
        fh.write(rendered.caption_text)

    canvas_width, canvas_height = canvas_size
    text_color = rendered.caption_color or "white"
    box_color = rendered.caption_background_color

    if rendered.caption_font_size and rendered.caption_reference_height:
        font_size = max(
            1,
            round(
                rendered.caption_font_size
                * canvas_height / rendered.caption_reference_height
            ),
        )
    else:
        font_size = rendered.caption_font_size or max(18, canvas_height // 20)

    if rendered.caption_x is not None:
        x_expr = f"(w*{rendered.caption_x / 100:.6f})-(text_w/2)"
    else:
        x_expr = "(w-text_w)/2"

    if rendered.caption_y is not None:
        y_expr = f"(h*{rendered.caption_y / 100:.6f})-(text_h/2)"
    else:
        y_expr = "h-text_h-(h*0.06)"

    parts = [
        f"textfile='{_escape_drawtext_path(text_path.replace(os.sep, '/'))}'",
        f"fontfile='{_escape_drawtext_path(font_file.replace(os.sep, '/'))}'",
        "expansion=none",
        f"fontsize={font_size}",
        f"fontcolor={text_color}",
        f"x={x_expr}",
        f"y={y_expr}",
    ]
    if box_color:
        parts += ["box=1", f"boxcolor={box_color}@0.75", "boxborderw=12"]

    return "drawtext=" + ":".join(parts)


@shared_task
def render_content(rendered_content_id):
    from apps.frames.models import RenderedContent

    rendered = RenderedContent.objects.select_related(
        "frame", "member__user", "source_video",
    ).filter(id=rendered_content_id).first()
    if rendered is None:
        return

    frame = rendered.frame
    source_video = rendered.source_video
    has_overlay = bool(frame.image)
    has_background = bool(frame.background)
    if (not has_overlay and not has_background) or not source_video.original_file:
        rendered.render_status = 3
        rendered.save()
        return

    is_animated_frame = has_overlay and frame.image.name.lower().endswith(".gif")
    is_video_content = source_video.media_type == 1

    has_trim = (
        is_video_content
        and rendered.trim_in is not None
        and rendered.trim_out is not None
        and rendered.trim_out > rendered.trim_in
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        content_path = os.path.join(tmp_dir, os.path.basename(source_video.original_file.name))
        with open(content_path, "wb") as fh:
            for chunk in source_video.original_file.chunks():
                fh.write(chunk)

        frame_path = None
        if has_overlay:
            frame_path = os.path.join(tmp_dir, os.path.basename(frame.image.name))
            with open(frame_path, "wb") as fh:
                for chunk in frame.image.chunks():
                    fh.write(chunk)

        background_path = None
        if has_background:
            background_path = os.path.join(tmp_dir, os.path.basename(frame.background.name))
            with open(background_path, "wb") as fh:
                for chunk in frame.background.chunks():
                    fh.write(chunk)

        if is_video_content:
            out_ext = ".mp4"
        elif is_animated_frame:
            out_ext = ".gif"
        else:
            out_ext = ".jpg"
        out_path = os.path.join(tmp_dir, f"{uuid4().hex}{out_ext}")

        reference_path = background_path or frame_path
        canvas_size = _capped_canvas(_probe_size(reference_path)) or _probe_size(reference_path) or (1080, 1920)

        pad_color = "black@0.0" if has_background else "black"

        if has_overlay:
            filter_complex = _content_graph(
                rendered, content_path, frame_path, canvas_size, pad_color,
            )
        else:
            filter_complex = _content_graph_no_overlay(
                rendered, content_path, canvas_size, pad_color,
            )
        final_label = "content"

        if has_background:
            background_index = 2 if has_overlay else 1
            filter_complex += (
                f";[{background_index}:v]scale={canvas_size[0]}:{canvas_size[1]}[bg]"
                f";[bg][{final_label}]overlay=0:0:shortest=1[layered]"
            )
            final_label = "layered"

        if has_overlay:
            if _overlay_is_transformed(rendered):
                (frame_w, frame_h), (frame_x, frame_y) = _overlay_transform(
                    rendered, canvas_size,
                )
                filter_complex += (
                    f";[frame]scale={frame_w}:{frame_h}[frame_fit]"
                    f";[{final_label}][frame_fit]"
                    f"overlay={frame_x}:{frame_y}:shortest=1[composited]"
                )
            else:
                filter_complex += (
                    f";[{final_label}][frame]overlay=0:0:shortest=1[composited]"
                )
            final_label = "composited"

        caption_filter = _caption_filter(rendered, canvas_size, tmp_dir)
        if caption_filter:
            filter_complex += f";[{final_label}]{caption_filter}[captioned]"
            final_label = "captioned"

        def build_inputs(content_args, background_args=None):
            cmd = ["ffmpeg", "-y", *content_args]
            if has_overlay:
                cmd += ["-ignore_loop", "0"] if is_animated_frame else ["-loop", "1"]
                cmd += ["-i", frame_path]
            if has_background:
                cmd += background_args if background_args is not None else ["-loop", "1"]
                cmd += ["-i", background_path]
            return cmd

        if is_video_content:
            content_args = []
            if has_trim:
                content_args += ["-ss", str(rendered.trim_in), "-t", str(rendered.trim_out - rendered.trim_in)]
            content_args += ["-i", content_path]
            cmd = build_inputs(content_args)
            cmd += [
                "-filter_complex", filter_complex,
                "-map", f"[{final_label}]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "26",
                "-pix_fmt", "yuv420p",
                out_path,
            ]
        elif is_animated_frame:
            frame_duration = _probe_duration(frame_path) or 1.0
            cmd = build_inputs(
                ["-loop", "1", "-t", str(frame_duration), "-i", content_path],
                background_args=["-loop", "1", "-t", str(frame_duration)] if has_background else None,
            )
            cmd += [
                "-filter_complex",
                f"{filter_complex};[{final_label}]fps=8,scale=480:-1:flags=lanczos,split[a][b]"
                ";[a]palettegen=stats_mode=diff[pal];[b][pal]paletteuse=dither=bayer",
                out_path,
            ]
        else:
            cmd = build_inputs(["-i", content_path])
            cmd += [
                "-filter_complex", filter_complex,
                "-map", f"[{final_label}]",
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

    if frame.frame_type == 2:
        expire_rendered_file.apply_async(
            args=[rendered.id], countdown=RENDER_EXPIRY_SECONDS,
        )

    notifications.notify(
        recipient=rendered.member.user,
        role=2,
        notification_type=6,
        title="Your framed content is ready",
        message=frame.name,
    )
