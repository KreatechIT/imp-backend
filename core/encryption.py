import os

from PIL import Image, UnidentifiedImageError
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ValidationError
from dotenv import load_dotenv


load_dotenv()
encryption_key = os.getenv("encryption_key")

cipher_suite = Fernet(encryption_key) if encryption_key else None


def _require_cipher():
    if cipher_suite is None:
        raise RuntimeError(
            "encryption_key is not set; add it to .env before using encryption."
        )
    return cipher_suite


def encrypt_value(value: str) -> str:
    return _require_cipher().encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    return _require_cipher().decrypt(token.encode()).decode()


def validate_file_size(value):
    limit = 10 * 1024 * 1024
    if value.size > limit:
        raise ValidationError("The maximum file size allowed is 10MB.")


def validate_content_file_size(value):
    """Finished reels are far bigger than an avatar or a banner."""
    limit = 200 * 1024 * 1024
    if value.size > limit:
        raise ValidationError("The maximum file size allowed is 200MB.")


def validate_transparent_image(value):
    """Reject a frame with no see-through area.

    A frame is an overlay. One saved without an alpha channel covers the
    whole video, which is the mistake worth catching at upload rather than
    after an influencer has already exported with it.
    """
    try:
        value.seek(0)
        image = Image.open(value)
        mode, info, image_format = image.mode, image.info, image.format
    except (UnidentifiedImageError, OSError):
        value.seek(0)
        raise ValidationError("The frame must be a valid image file.")

    value.seek(0)

    if image_format not in ("PNG", "GIF"):
        raise ValidationError("The frame must be a PNG or GIF image.")

    has_alpha = mode in ("RGBA", "LA") or (
        mode == "P" and "transparency" in info
    )
    if not has_alpha:
        raise ValidationError(
            "The frame must have a transparent area. An image without "
            "transparency would cover the whole video."
        )


def build_image_url(image_str):
    if not image_str:
        return None
    image_structure = settings.IMAGE_STRUCTURE
    return f"{image_structure}{image_str}"
