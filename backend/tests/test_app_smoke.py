"""End-to-end HTTP smoke through the real app (lifespan → migrations → routers).

Runs on a temp SQLite file by default; in CI it also runs against a Postgres service
via TEST_DATABASE_URL. Covers the auth seam over HTTP: local mode needs no token,
cloud mode rejects missing/invalid tokens and accepts a valid one.
"""
import os
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app import auth, database
from app import main as app_main
from app.config import settings
from app.database import Base
from app.services.blob_storage import get_blob_storage

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture
def client(tmp_path, monkeypatch):
    if TEST_DATABASE_URL:
        eng = create_engine(TEST_DATABASE_URL)
        with eng.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE'))
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    else:
        eng = create_engine(
            f"sqlite:///{tmp_path / 'smoke.db'}", connect_args={"check_same_thread": False}
        )
    # The app's engine is module-level; point lifespan and sessions at ours.
    monkeypatch.setattr(app_main, "engine", eng)
    database.SessionLocal.configure(bind=eng)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    get_blob_storage.cache_clear()
    with TestClient(app_main.app) as c:
        yield c
    database.SessionLocal.configure(bind=database.engine)
    get_blob_storage.cache_clear()
    eng.dispose()


def test_local_mode_end_to_end(client):
    health = client.get("/api/health").json()
    assert health["status"] == "ok" and health["auth_mode"] == "local"
    assert health["storage_backend"] == "local"

    assert client.get("/api/preferences/status").json() == {"onboarded": False}

    r = client.post(
        "/api/inventory",
        json={"name": "Milk", "quantity": 1, "unit": "quart", "category": "dairy", "storage": "fridge"},
    )
    assert r.status_code == 201 and r.json()["name"] == "milk"
    assert [i["name"] for i in client.get("/api/inventory").json()] == ["milk"]

    prefs = client.get("/api/preferences").json()
    prefs.update({"name": "Chris", "location": "Seattle"})
    body = {k: prefs[k] for k in (
        "name", "household_size", "allergies", "dietary_restrictions", "equipment",
        "max_complexity", "disliked_ingredients", "disliked_cuisines", "no_repeat_days",
        "location", "pantry_staples",
    )}
    r = client.put("/api/preferences", json=body)
    assert r.status_code == 200 and r.json()["onboarded"] is True
    assert client.get("/api/preferences/status").json() == {"onboarded": True}

    assert client.get("/api/meals").json() == []
    assert client.get("/api/meals/delivery/status").json()["used"] is False
    assert client.get("/api/plans/current").status_code == 404
    assert client.post("/api/shopping-list", json={"name": "Lemons", "unit": "piece"}).status_code == 201
    assert client.get("/api/inventory/extract/999/image").status_code == 404


@pytest.fixture
def cloud_mode(monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = private.public_key()

    class _Key:
        key = public

    class _Stub:
        def get_signing_key_from_jwt(self, token):
            return _Key()

    monkeypatch.setattr(settings, "supabase_url", "https://abc123.supabase.co")
    monkeypatch.setattr(auth, "_jwk_client", lambda: _Stub())

    def token(sub="8d3f1c2e-1111-4a2b-9c3d-000000000042", **over):
        now = int(time.time())
        claims = {
            "iss": "https://abc123.supabase.co/auth/v1", "aud": "authenticated", "sub": sub,
            "email": f"{sub[:8]}@example.com", "iat": now, "exp": now + 600, **over,
        }
        return jwt.encode(claims, pem, algorithm="ES256", headers={"kid": "k1"})

    return token


def test_cloud_mode_over_http(client, cloud_mode):
    assert client.get("/api/health").json()["auth_mode"] == "supabase"

    r = client.get("/api/inventory")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    assert client.get("/api/inventory", headers={"Authorization": "Bearer nope"}).status_code == 401

    alice = {"Authorization": f"Bearer {cloud_mode()}"}
    bob = {"Authorization": f"Bearer {cloud_mode(sub='9e4a2d3f-2222-4b3c-8d4e-000000000099')}"}

    r = client.post("/api/inventory", json={"name": "Tofu", "unit": "pack"}, headers=alice)
    assert r.status_code == 201
    assert [i["name"] for i in client.get("/api/inventory", headers=alice).json()] == ["tofu"]
    assert client.get("/api/inventory", headers=bob).json() == []
    assert client.delete(f"/api/inventory/{r.json()['id']}", headers=bob).status_code == 404
    assert client.delete(f"/api/inventory/{r.json()['id']}", headers=alice).status_code == 204

    # Each account gets its own preferences row, created on first touch.
    assert client.get("/api/preferences", headers=alice).json()["id"] != \
        client.get("/api/preferences", headers=bob).json()["id"]
    # Health stays open.
    assert client.get("/api/health").status_code == 200
