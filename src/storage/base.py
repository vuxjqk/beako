from typing import Protocol


class Storage(Protocol):
    def save(self, key: str, data: bytes) -> str:
        """Store data under key (e.g. "avatars/abc.webp") and return its public URL."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object; no error if it doesn't exist."""
        ...

    def key_from_url(self, url: str) -> str | None:
        """Key of a URL this storage produced, or None for foreign URLs (e.g. Google avatars)."""
        ...
