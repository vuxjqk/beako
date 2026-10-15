import mimetypes
import os
import tempfile
from pathlib import Path

# Python < 3.13 has no built-in mapping and the slim image ships no /etc/mime.types,
# so StaticFiles would otherwise serve avatars with the wrong content-type
mimetypes.add_type("image/webp", ".webp")


class LocalStorage:
    """Files on local disk, served by the app's /media static mount."""

    def __init__(self, root: str | Path, base_url: str) -> None:
        self.root = Path(root).resolve()
        self.base_url = base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Key escapes storage root: {key!r}")
        return path

    def save(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file then rename, so readers never see a partial file
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return f"{self.base_url}/{key}"

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def key_from_url(self, url: str) -> str | None:
        prefix = f"{self.base_url}/"
        return url[len(prefix):] if url.startswith(prefix) else None
