"""In-memory object storage for tests (same interface as MinioObjectStore)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryObjectStore:
    objects: dict[str, tuple[bytes, str]] = field(default_factory=dict)
    fail_on_put: bool = False

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        if self.fail_on_put:
            raise ConnectionError("storage down")
        self.objects[key] = (data, content_type)

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def download_url(self, key: str, *, expires_seconds: int) -> str:
        return f"https://storage.example/{key}?expires={expires_seconds}"
