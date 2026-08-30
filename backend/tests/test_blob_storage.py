"""Blob storage backends + the image route that fronts them."""
import json

import httpx
import pytest
from conftest import LOCAL_USER, OTHER_USER
from fastapi import HTTPException
from fastapi.responses import RedirectResponse, Response

from app import models
from app.config import settings
from app.routers import inventory
from app.services import blob_storage
from app.services.blob_storage import LocalDiskStorage, SupabaseStorage, get_blob_storage

JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


# --- local disk -----------------------------------------------------------------


def test_local_round_trip(tmp_path):
    store = LocalDiskStorage(str(tmp_path / "uploads"))
    key = store.save_image(JPEG, user_id=LOCAL_USER.id)
    assert key.endswith(".jpg") and "/" not in key
    assert store.load_image(key) == JPEG
    assert store.signed_url(key) is None
    assert store.load_image("nope.jpg") is None


def test_local_honours_legacy_absolute_paths(tmp_path):
    legacy = tmp_path / "old.jpg"
    legacy.write_bytes(JPEG)
    store = LocalDiskStorage(str(tmp_path / "uploads"))
    assert store.load_image(str(legacy)) == JPEG


# --- supabase -------------------------------------------------------------------


def _supabase(handler):
    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"apikey": "sb_secret_x", "Authorization": "Bearer sb_secret_x"},
    )
    return SupabaseStorage("https://abc.supabase.co/", "sb_secret_x", "fridge-photos", client=client)


def test_supabase_upload_and_sign():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "POST" and "/object/sign/" in request.url.path:
            key = request.url.path.split("/object/sign/fridge-photos/")[1]
            return httpx.Response(200, json={"signedURL": f"/object/sign/fridge-photos/{key}?token=t"})
        if request.method == "POST" and "/object/fridge-photos/" in request.url.path:
            return httpx.Response(200, json={"Key": "fridge-photos/x"})
        return httpx.Response(404)

    store = _supabase(handler)
    key = store.save_image(JPEG, user_id=OTHER_USER.id)
    assert key.startswith(f"{OTHER_USER.id}/") and key.endswith(".jpg")

    upload = calls[0]
    assert upload.url == f"https://abc.supabase.co/storage/v1/object/fridge-photos/{key}"
    assert upload.headers["content-type"] == "image/jpeg"
    assert upload.headers["authorization"] == "Bearer sb_secret_x"
    assert upload.headers["x-upsert"] == "false"
    assert upload.content == JPEG

    url = store.signed_url(key, expires_s=120)
    assert url == f"https://abc.supabase.co/storage/v1/object/sign/fridge-photos/{key}?token=t"
    assert json.loads(calls[1].content) == {"expiresIn": 120}


def test_supabase_upload_failure_raises():
    store = _supabase(lambda r: httpx.Response(403, json={"message": "nope"}))
    with pytest.raises(RuntimeError, match="403"):
        store.save_image(JPEG, user_id=LOCAL_USER.id)


def test_supabase_load_and_missing():
    def handler(request):
        if request.url.path.endswith("/have.jpg"):
            return httpx.Response(200, content=JPEG)
        return httpx.Response(404, json={"error": "not found"})

    store = _supabase(handler)
    assert store.load_image("u/have.jpg") == JPEG
    assert store.load_image("u/missing.jpg") is None


def test_supabase_sign_failure_falls_back_to_none():
    store = _supabase(lambda r: httpx.Response(400, json={"error": "bad"}))
    assert store.signed_url("u/x.jpg") is None


# --- backend selection ------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_backend_cache():
    get_blob_storage.cache_clear()
    yield
    get_blob_storage.cache_clear()


def test_backend_auto_local_by_default(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "")
    assert isinstance(get_blob_storage(), LocalDiskStorage)


def test_backend_auto_supabase_in_cloud_mode(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://abc.supabase.co")
    monkeypatch.setattr(settings, "supabase_secret_key", "sb_secret_x")
    assert isinstance(get_blob_storage(), SupabaseStorage)


def test_backend_forced_supabase_needs_key(monkeypatch):
    monkeypatch.setattr(settings, "blob_backend", "supabase")
    monkeypatch.setattr(settings, "supabase_secret_key", "")
    with pytest.raises(RuntimeError):
        get_blob_storage()


# --- image route ------------------------------------------------------------------


class _Stub:
    def __init__(self, url=None, data=None):
        self.url, self.data = url, data

    def signed_url(self, key, expires_s=300):
        return self.url

    def load_image(self, key):
        return self.data


def _batch(db, user=LOCAL_USER, key="k.jpg"):
    batch = models.ExtractionBatch(user_id=user.id, image_key=key, status="pending_review")
    db.add(batch)
    db.commit()
    return batch


def test_image_route_redirects_to_signed_url(db, monkeypatch):
    batch = _batch(db)
    monkeypatch.setattr(inventory, "get_blob_storage", lambda: _Stub(url="https://signed/x"))
    resp = inventory.get_extraction_image(batch.id, user=LOCAL_USER, db=db)
    assert isinstance(resp, RedirectResponse) and resp.status_code == 302
    assert resp.headers["location"] == "https://signed/x"


def test_image_route_streams_when_unsigned(db, monkeypatch):
    batch = _batch(db)
    monkeypatch.setattr(inventory, "get_blob_storage", lambda: _Stub(data=JPEG))
    resp = inventory.get_extraction_image(batch.id, user=LOCAL_USER, db=db)
    assert isinstance(resp, Response) and resp.body == JPEG
    assert resp.media_type == "image/jpeg"


def test_image_route_404s_when_missing_or_foreign(db, monkeypatch):
    batch = _batch(db)
    monkeypatch.setattr(inventory, "get_blob_storage", lambda: _Stub())
    with pytest.raises(HTTPException) as exc:
        inventory.get_extraction_image(batch.id, user=LOCAL_USER, db=db)
    assert exc.value.status_code == 404
    monkeypatch.setattr(inventory, "get_blob_storage", lambda: _Stub(data=JPEG))
    with pytest.raises(HTTPException) as exc:
        inventory.get_extraction_image(batch.id, user=OTHER_USER, db=db)
    assert exc.value.status_code == 404


def test_default_backend_is_local_disk_module_level():
    assert blob_storage._backend_name() == "local"
