"""Where uploaded fridge photos live.

* `LocalDiskStorage` — files under `settings.upload_dir` (the `data/uploads` Docker
  volume). Default in local mode.
* `SupabaseStorage` — a private Supabase Storage bucket, keyed `<user_id>/<uuid>.jpg`,
  written with the backend's secret key and served through short-lived signed URLs.
  Default in cloud mode.

Both are reached via `get_blob_storage()`. Keys are opaque strings stored on
`ExtractionBatch.image_key`; the client-facing URL is always the backend route
`/api/inventory/extract/{id}/image`, so the frontend never knows which backend is in use.

Unlike Brave, storage is **not** fail-soft: a failed upload surfaces as a 502 from the
extract endpoint (the same as an AI failure), because a batch without its photo is
useless.
"""
import logging
import os
import uuid
from functools import lru_cache
from typing import Protocol

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class BlobStorage(Protocol):
    def save_image(self, data: bytes, *, user_id: str) -> str:
        """Persist JPEG bytes; return the storage key."""

    def load_image(self, key: str) -> bytes | None:
        """Return the bytes for `key`, or None if missing."""

    def signed_url(self, key: str, expires_s: int = 300) -> str | None:
        """A time-limited URL a browser can GET directly, or None to stream instead."""

    def check(self) -> None:
        """Startup sanity check; log (don't raise) on problems."""


class LocalDiskStorage:
    def __init__(self, root: str | None = None):
        self.root = root or settings.upload_dir

    def save_image(self, data: bytes, *, user_id: str) -> str:
        os.makedirs(self.root, exist_ok=True)
        key = f"{uuid.uuid4().hex}.jpg"
        with open(os.path.join(self.root, key), "wb") as fh:
            fh.write(data)
        return key

    def _path(self, key: str) -> str:
        # Rows from before the storage abstraction hold absolute paths; honour them.
        return key if os.path.isabs(key) else os.path.join(self.root, key)

    def load_image(self, key: str) -> bytes | None:
        path = self._path(key)
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as fh:
            return fh.read()

    def signed_url(self, key: str, expires_s: int = 300) -> str | None:
        return None

    def check(self) -> None:
        try:
            os.makedirs(self.root, exist_ok=True)
        except OSError as exc:
            logger.warning(
                "Upload directory %r is not writable (%s); photo uploads will fail until "
                "UPLOAD_DIR points somewhere writable.", self.root, exc
            )


class SupabaseStorage:
    """Thin client for the Storage REST API (two endpoints; no SDK needed)."""

    def __init__(
        self,
        base_url: str,
        secret_key: str,
        bucket: str,
        client: httpx.Client | None = None,
    ):
        self.base = f"{base_url.rstrip('/')}/storage/v1"
        self.bucket = bucket
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(20.0),
            headers={"apikey": secret_key, "Authorization": f"Bearer {secret_key}"},
        )

    def _object_url(self, key: str) -> str:
        return f"{self.base}/object/{self.bucket}/{key}"

    def save_image(self, data: bytes, *, user_id: str) -> str:
        key = f"{user_id}/{uuid.uuid4().hex}.jpg"
        resp = self._client.post(
            self._object_url(key),
            content=data,
            headers={"Content-Type": "image/jpeg", "x-upsert": "false"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Supabase Storage upload failed ({resp.status_code}): {resp.text[:200]}"
            )
        return key

    def load_image(self, key: str) -> bytes | None:
        resp = self._client.get(self._object_url(key))
        if resp.status_code == 200:
            return resp.content
        if resp.status_code in (400, 404):
            return None
        raise RuntimeError(
            f"Supabase Storage download failed ({resp.status_code}): {resp.text[:200]}"
        )

    def signed_url(self, key: str, expires_s: int = 300) -> str | None:
        resp = self._client.post(
            f"{self.base}/object/sign/{self.bucket}/{key}",
            json={"expiresIn": expires_s},
        )
        if resp.status_code != 200:
            logger.warning(
                "Could not sign %s (%s): %s", key, resp.status_code, resp.text[:200]
            )
            return None
        path = resp.json().get("signedURL", "")
        return f"{self.base}{path}" if path.startswith("/") else path

    def check(self) -> None:
        try:
            resp = self._client.get(f"{self.base}/bucket/{self.bucket}")
        except httpx.HTTPError as exc:
            logger.warning("Supabase Storage unreachable: %s", exc)
            return
        if resp.status_code != 200:
            logger.warning(
                "Supabase Storage bucket %r not accessible (%s). Create a PRIVATE bucket "
                "with that name in the Supabase dashboard.",
                self.bucket,
                resp.status_code,
            )
        elif resp.json().get("public"):
            logger.warning("Supabase Storage bucket %r is PUBLIC; it should be private.", self.bucket)


def _backend_name() -> str:
    if settings.blob_backend in ("local", "supabase"):
        return settings.blob_backend
    return "supabase" if (settings.auth_enabled and settings.supabase_secret_key) else "local"


@lru_cache(maxsize=1)
def get_blob_storage() -> BlobStorage:
    if _backend_name() == "supabase":
        if not settings.supabase_secret_key:
            raise RuntimeError("BLOB_BACKEND=supabase requires SUPABASE_SECRET_KEY")
        return SupabaseStorage(
            settings.supabase_url, settings.supabase_secret_key, settings.supabase_storage_bucket
        )
    return LocalDiskStorage()
