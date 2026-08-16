import os

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


def build_image_url(image_str):
    if not image_str:
        return None
    image_structure = settings.IMAGE_STRUCTURE
    return f"{image_structure}{image_str}"
