"""The auth seam: local mode, Supabase JWT verification, and per-user scoping."""
import time

import jwt
import pytest
from conftest import LOCAL_USER, OTHER_USER
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app import auth, models
from app.config import settings
from app.routers import inventory, meals, shopping
from app.services.scope import get_owned, get_prefs

# --- local mode ---------------------------------------------------------------


def test_local_mode_resolves_fixed_user_and_creates_row(db):
    db.query(models.User).delete()
    db.commit()
    user = auth.get_current_user(creds=None, db=db)
    assert user.id == LOCAL_USER.id
    assert db.get(models.User, LOCAL_USER.id) is not None


def test_local_mode_ignores_any_bearer(db):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="whatever")
    assert auth.get_current_user(creds=creds, db=db).id == LOCAL_USER.id


def test_get_prefs_creates_per_user_with_staples(db):
    a = get_prefs(db, LOCAL_USER.id)
    b = get_prefs(db, OTHER_USER.id)
    assert a.id != b.id and a.pantry_staples and b.pantry_staples
    assert get_prefs(db, LOCAL_USER.id).id == a.id  # idempotent


# --- scoping ------------------------------------------------------------------


def test_inventory_does_not_bleed_between_users(db):
    db.add(models.InventoryItem(user_id=LOCAL_USER.id, name="milk", storage="fridge"))
    db.add(models.InventoryItem(user_id=OTHER_USER.id, name="tofu", storage="fridge"))
    db.commit()
    assert [i.name for i in inventory.list_inventory(user=LOCAL_USER, db=db)] == ["milk"]
    assert [i.name for i in inventory.list_inventory(user=OTHER_USER, db=db)] == ["tofu"]


def test_get_owned_404s_across_users(db):
    item = models.InventoryItem(user_id=LOCAL_USER.id, name="milk", storage="fridge")
    db.add(item)
    db.commit()
    assert get_owned(db, models.InventoryItem, item.id, LOCAL_USER.id, label="Item") is item
    with pytest.raises(HTTPException) as exc:
        inventory.delete_item(item.id, user=OTHER_USER, db=db)
    assert exc.value.status_code == 404
    assert db.get(models.InventoryItem, item.id) is not None


def test_delivery_quota_is_per_user(db):
    db.add(models.Meal(
        user_id=OTHER_USER.id, title="Pho", title_normalized="pho", recipe_json={},
        status="ordered", delivery_ordered_at=models.utcnow(),
    ))
    db.commit()
    assert meals.delivery_status(user=OTHER_USER, db=db).used is True
    assert meals.delivery_status(user=LOCAL_USER, db=db).used is False


def test_shopping_list_is_per_user(db):
    db.add(models.ShoppingListItem(user_id=OTHER_USER.id, name="tofu", checked=True))
    db.commit()
    assert shopping.list_shopping(user=LOCAL_USER, db=db) == []
    assert shopping.checked_to_inventory(user=LOCAL_USER, db=db) == []
    assert len(shopping.list_shopping(user=OTHER_USER, db=db)) == 1


# --- cloud mode: Supabase JWT verification --------------------------------------

PROJECT_URL = "https://abc123.supabase.co"


@pytest.fixture
def keypair():
    private = ec.generate_private_key(ec.SECP256R1())
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return private_pem, private.public_key()


@pytest.fixture
def cloud_mode(monkeypatch, keypair):
    """Flip settings into cloud mode and stub the JWKS client with our test key."""
    _, public_key = keypair

    class _Key:
        key = public_key

    class _StubJwkClient:
        def get_signing_key_from_jwt(self, token):
            return _Key()

    monkeypatch.setattr(settings, "supabase_url", PROJECT_URL)
    monkeypatch.setattr(auth, "_jwk_client", lambda: _StubJwkClient())
    yield


def _token(private_pem, **overrides):
    now = int(time.time())
    claims = {
        "iss": f"{PROJECT_URL}/auth/v1",
        "aud": "authenticated",
        "sub": "8d3f1c2e-1111-4a2b-9c3d-000000000042",
        "email": "chris@example.com",
        "role": "authenticated",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, private_pem, algorithm="ES256", headers={"kid": "k1"})


def test_valid_token_resolves_user_and_upserts(cloud_mode, keypair, db):
    private_pem, _ = keypair
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_token(private_pem))
    user = auth.get_current_user(creds=creds, db=db)
    assert user.id == "8d3f1c2e-1111-4a2b-9c3d-000000000042"
    assert user.email == "chris@example.com"
    row = db.get(models.User, user.id)
    assert row is not None and row.email == "chris@example.com"
    # Second request: same row, no duplicate.
    auth.get_current_user(creds=creds, db=db)
    assert db.query(models.User).filter_by(id=user.id).count() == 1


def test_missing_token_is_401_with_challenge(cloud_mode, db):
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(creds=None, db=db)
    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 10},  # expired
        {"aud": "anon"},  # wrong audience
        {"iss": "https://evil.example/auth/v1"},  # wrong issuer
        {"sub": None},  # required claim missing
    ],
)
def test_bad_tokens_are_rejected(cloud_mode, keypair, db, overrides):
    private_pem, _ = keypair
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=_token(private_pem, **overrides)
    )
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(creds=creds, db=db)
    assert exc.value.status_code == 401


def test_hs256_token_is_rejected(cloud_mode, db):
    token = jwt.encode({"sub": "x", "aud": "authenticated"}, "shared-secret-that-is-at-least-32-bytes-long", algorithm="HS256")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(creds=creds, db=db)
    assert exc.value.status_code == 401


def test_token_signed_by_other_key_is_rejected(cloud_mode, db):
    other_pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=_token(other_pem))
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(creds=creds, db=db)
    assert exc.value.status_code == 401


def test_settings_derived_urls():
    assert settings.auth_enabled is False  # default: local mode
    s = settings.model_copy(update={"supabase_url": PROJECT_URL + "/"})
    assert s.auth_enabled
    assert s.supabase_issuer == f"{PROJECT_URL}/auth/v1"
    assert s.supabase_jwks_url == f"{PROJECT_URL}/auth/v1/.well-known/jwks.json"
