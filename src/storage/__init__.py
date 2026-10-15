from functools import lru_cache

from src.core.config import settings
from src.storage.base import Storage
from src.storage.local import LocalStorage


@lru_cache
def get_storage() -> Storage:
    # Swap for another Storage implementation (S3, Cloudinary, ...) here
    return LocalStorage(settings.MEDIA_ROOT, settings.MEDIA_URL)


__all__ = ["Storage", "LocalStorage", "get_storage"]
