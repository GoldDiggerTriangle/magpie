from abc import ABC, abstractmethod
from pathlib import Path

from django.conf import settings


class FileStorageAdapter(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        raise NotImplementedError

    @abstractmethod
    def open(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def url(self, key: str) -> str:
        raise NotImplementedError


class LocalFileStorageAdapter(FileStorageAdapter):
    def __init__(self, root: Path | None = None, base_url: str = "/media/"):
        self.root = Path(root or settings.MEDIA_ROOT)
        self.base_url = base_url

    def save(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def open(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def delete(self, key: str) -> None:
        path = self.root / key
        if path.exists():
            path.unlink()

    def url(self, key: str) -> str:
        return f"{self.base_url}{key}"
