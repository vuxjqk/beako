import io
import logging
import uuid
import warnings

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from src.core.config import settings
from src.models import User
from src.storage import get_storage

logger = logging.getLogger(__name__)

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Reject decompression bombs: a tiny file that expands to a huge bitmap
Image.MAX_IMAGE_PIXELS = 25_000_000

FILE_TOO_LARGE = HTTPException(
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    f"Avatar must be at most {settings.AVATAR_MAX_BYTES // (1024 * 1024)} MB",
)
UNSUPPORTED_TYPE = HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Avatar must be a JPEG, PNG or WebP image")
INVALID_IMAGE = HTTPException(status.HTTP_400_BAD_REQUEST, "File is not a valid image")


def _read_limited(upload: UploadFile) -> bytes:
    data = upload.file.read(settings.AVATAR_MAX_BYTES + 1)
    if len(data) > settings.AVATAR_MAX_BYTES:
        raise FILE_TOO_LARGE
    if not data:
        raise INVALID_IMAGE
    return data


def _process_image(raw: bytes) -> bytes:
    """Validate by content (not the client's content-type), square-crop, resize and re-encode to WebP.

    Re-encoding drops EXIF (GPS etc.) and anything smuggled inside the original file.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as img:
                if img.format not in ALLOWED_FORMATS:
                    raise UNSUPPORTED_TYPE
                img.load()
                img = ImageOps.exif_transpose(img)
                side = min(settings.AVATAR_SIZE, img.width, img.height)
                img = ImageOps.fit(img, (side, side), Image.Resampling.LANCZOS)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA" if "transparency" in img.info or "A" in img.mode else "RGB")
                out = io.BytesIO()
                img.save(out, "WEBP", quality=85)
                return out.getvalue()
    except HTTPException:
        raise
    except UnidentifiedImageError:
        raise UNSUPPORTED_TYPE
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError):
        raise INVALID_IMAGE


def _delete_owned_file(url: str | None) -> None:
    if not url:
        return
    storage = get_storage()
    key = storage.key_from_url(url)
    if key is None:
        return  # external URL (e.g. Google picture), nothing to delete
    try:
        storage.delete(key)
    except Exception:
        logger.exception("Failed to delete old avatar %s", key)


def update_avatar(db: Session, user: User, upload: UploadFile) -> User:
    """Store the new avatar, commit, then remove the previous file (commits the session)."""
    data = _process_image(_read_limited(upload))
    storage = get_storage()
    key = f"avatars/{uuid.uuid4().hex}.webp"
    new_url = storage.save(key, data)

    old_url = user.avatar
    user.avatar = new_url
    try:
        db.commit()
    except Exception:
        storage.delete(key)
        raise
    _delete_owned_file(old_url)
    return user


def remove_avatar(db: Session, user: User) -> User:
    """Clear the avatar, commit, then remove its file (commits the session)."""
    old_url = user.avatar
    if old_url is None:
        return user
    user.avatar = None
    db.commit()
    _delete_owned_file(old_url)
    return user
