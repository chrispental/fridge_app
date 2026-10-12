"""The delegated-token boundary is distinct from first-party Supabase sessions.

All signing keys, grants and users are synthetic. JWKS is stubbed, so these tests
never call an identity provider or touch a real kitchen.
"""
import secrets
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastmcp.server.auth import AccessToken, TokenVerifier
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, mcp_auth, models
from app.config import DEFAULT_LOCAL_USER_ID, Settings, settings
from app.database import Base

RESOURCE = "https://fridge.example/mcp"
ISSUER = "https://identity.example/"
SUBJECT = "oauth-subject-alice"
CLIENT = "approved-chat-client"
USER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_USER_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_config(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "mcp_enabled", True)
    monkeypatch.setattr(settings, "mcp_resource_url", RESOURCE)
    monkeypatch.setattr(settings, "mcp_issuer_url", ISSUER)
    monkeypatch.setattr(settings, "mcp_jwks_url", "https://identity.example/jwks.json")
    monkeypatch.setattr(settings, "mcp_grants", [{
        "subject": SUBJECT,
        "client_id": CLIENT,
        "user_id": USER_ID,
        "scopes": [mcp_auth.READ_SCOPE, mcp_auth.WRITE_SCOPE],
    }])


@pytest.fixture
def isolated_sessions(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all([models.User(id=USER_ID), models.User(id=OTHER_USER_ID)])
        db.commit()
    monkeypatch.setattr(mcp_auth, "SessionLocal", sessions)
    yield sessions
    engine.dispose()


@pytest.fixture
def token_factory(monkeypatch, mcp_config, isolated_sessions):
    private_key = ec.generate_private_key(ec.SECP256R1())

    class FakeJwks:
        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=private_key.public_key())

    monkeypatch.setattr(mcp_auth, "_jwk_client", lambda url: FakeJwks())
    monkeypatch.setattr(auth, "_jwk_client", lambda: FakeJwks())

    def issue(*, headers=None, omit=(), **overrides):
        now = int(time.time())
        claims = {
            "iss": ISSUER, "aud": RESOURCE, "sub": SUBJECT, "client_id": CLIENT,
            "scope": "fridge:read fridge:shopping", "iat": now, "exp": now + 300,
            "jti": "synthetic-access-token-id",
            **overrides,
        }
        for key in omit:
            claims.pop(key, None)
        return jwt.encode(
            claims, private_key, algorithm="ES256",
            headers={"kid": "synthetic-test-key", "typ": "at+jwt", **(headers or {})},
        )

    return issue


def test_mcp_is_disabled_by_default():
    assert Settings.model_fields["mcp_enabled"].default is False


def test_verifier_uses_fastmcp_auth_contract():
    verifier = mcp_auth.FridgeTokenVerifier()
    assert isinstance(verifier, TokenVerifier)
    assert verifier.required_scopes == [mcp_auth.READ_SCOPE]


def test_valid_configuration_requires_explicit_mapping(mcp_config):
    mcp_auth.validate_configuration()
    grant = mcp_auth.validated_grants()[(SUBJECT, CLIENT)]
    assert grant.user_id == USER_ID
    assert grant.scopes == {"fridge:read", "fridge:shopping"}


@pytest.mark.parametrize("field,value", [
    ("supabase_url", ""),
    ("mcp_resource_url", "http://fridge.example/mcp"),
    ("mcp_resource_url", "https://fridge.example/mcp/"),
    ("mcp_resource_url", "https://fridge.example/api"),
    ("mcp_resource_url", "https://user:password@fridge.example/mcp"),
    ("mcp_resource_url", "https://fridge.example/mcp?token=bad"),
    ("mcp_resource_url", "https://fridge.example/mcp#fragment"),
    ("mcp_issuer_url", "http://identity.example/"),
    ("mcp_issuer_url", "https://project.supabase.co/auth/v1"),
    ("mcp_jwks_url", "http://identity.example/jwks.json"),
    ("mcp_jwks_url", "/jwks.json"),
])
def test_unsafe_configuration_is_rejected(mcp_config, monkeypatch, field, value):
    monkeypatch.setattr(settings, field, value)
    with pytest.raises(ValueError):
        mcp_auth.validate_configuration()


@pytest.mark.parametrize("override", [
    {"subject": ""},
    {"client_id": ""},
    {"client_id": 7},
    {"user_id": "not-a-uuid"},
    {"user_id": DEFAULT_LOCAL_USER_ID},
    {"scopes": "fridge:read"},
    {"scopes": ["fridge:shopping"]},
    {"scopes": ["fridge:read", "admin"]},
    {"scopes": ["fridge:read", 1]},
    {"unexpected": "field"},
])
def test_invalid_grants_are_rejected(mcp_config, monkeypatch, override):
    monkeypatch.setattr(settings, "mcp_grants", [{**settings.mcp_grants[0], **override}])
    with pytest.raises(ValueError):
        mcp_auth.validate_configuration()


@pytest.mark.parametrize("count", [0, 2, 1001])
def test_missing_duplicate_or_excessive_grants_are_rejected(mcp_config, monkeypatch, count):
    monkeypatch.setattr(settings, "mcp_grants", settings.mcp_grants * count)
    with pytest.raises(ValueError):
        mcp_auth.validate_configuration()


def test_valid_token_resolves_only_the_explicit_app_user(token_factory):
    token = token_factory(app_user_id=OTHER_USER_ID, user_id=OTHER_USER_ID)
    verified = mcp_auth.FridgeTokenVerifier()._verify(token)
    assert isinstance(verified, AccessToken)
    assert verified.token == token
    assert verified.client_id == CLIENT
    assert verified.subject == SUBJECT
    assert verified.resource == RESOURCE
    assert verified.claims == {"iss": ISSUER, "app_user_id": USER_ID}
    assert set(verified.scopes) == {"fridge:read", "fridge:shopping"}


@pytest.mark.anyio
async def test_async_verifier_uses_isolated_database(token_factory):
    verified = await mcp_auth.FridgeTokenVerifier().verify_token(token_factory())
    assert verified is not None
    assert verified.claims["app_user_id"] == USER_ID


def test_rs256_is_also_supported(token_factory, monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(mcp_auth, "_jwk_client", lambda url: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key()),
    ))
    now = int(time.time())
    token = jwt.encode({
        "iss": ISSUER, "aud": RESOURCE, "sub": SUBJECT, "client_id": CLIENT,
        "scope": "fridge:read", "iat": now, "exp": now + 300, "jti": "synthetic-rsa-id",
    }, private_key, algorithm="RS256", headers={"typ": "at+jwt"})
    assert mcp_auth.FridgeTokenVerifier()._verify(token) is not None


@pytest.mark.parametrize("overrides", [
    {"aud": "authenticated"},
    {"aud": RESOURCE + "/"},
    {"aud": [RESOURCE]},
    {"aud": [RESOURCE, "https://another.example/mcp"]},
    {"iss": "https://project.supabase.co/auth/v1"},
    {"iss": "https://attacker.example/"},
    {"sub": "unmapped-subject"},
    {"sub": USER_ID},
    {"client_id": "unapproved-client"},
    {"client_id": 7},
    {"scope": ["fridge:read"]},
    {"scope": "fridge:shopping"},
    {"scope": ""},
    {"jti": ""},
    {"jti": 7},
    {"exp": 1},
])
def test_wrong_token_claims_are_rejected(token_factory, overrides):
    assert mcp_auth.FridgeTokenVerifier()._verify(token_factory(**overrides)) is None


@pytest.mark.parametrize("claim", ["iss", "aud", "sub", "client_id", "scope", "iat", "exp", "jti"])
def test_required_claims_cannot_be_omitted(token_factory, claim):
    assert mcp_auth.FridgeTokenVerifier()._verify(token_factory(omit=[claim])) is None


@pytest.mark.parametrize("typ", ["JWT", "id+jwt", "AT+JWT", None])
def test_non_access_token_types_are_rejected(token_factory, typ):
    assert mcp_auth.FridgeTokenVerifier()._verify(token_factory(headers={"typ": typ})) is None


def test_explicit_application_access_token_type_is_accepted(token_factory):
    assert mcp_auth.FridgeTokenVerifier()._verify(token_factory(headers={"typ": "application/at+jwt"})) is not None


def test_future_and_overlong_lifetimes_are_rejected(token_factory):
    now = int(time.time())
    verifier = mcp_auth.FridgeTokenVerifier()
    assert verifier._verify(token_factory(iat=now + 120, exp=now + 300)) is None
    assert verifier._verify(token_factory(iat=now, exp=now + 901)) is None
    assert verifier._verify(token_factory(iat=now, exp=now + 900)) is not None


@pytest.mark.parametrize("claim,convert", [
    ("iat", bool), ("iat", float), ("iat", str),
    ("exp", bool), ("exp", float), ("exp", str),
])
def test_numeric_dates_must_be_integer_values(token_factory, claim, convert):
    now = int(time.time())
    claims = {"iat": now, "exp": now + 300}
    claims[claim] = convert(claims[claim])
    assert mcp_auth.FridgeTokenVerifier()._verify(token_factory(**claims)) is None


def test_invalid_signature_is_rejected(token_factory):
    other_key = ec.generate_private_key(ec.SECP256R1())
    now = int(time.time())
    token = jwt.encode({
        "iss": ISSUER, "aud": RESOURCE, "sub": SUBJECT, "client_id": CLIENT,
        "scope": "fridge:read", "iat": now, "exp": now + 300, "jti": "synthetic-wrong-key-id",
    }, other_key, algorithm="ES256", headers={"typ": "at+jwt"})
    assert mcp_auth.FridgeTokenVerifier()._verify(token) is None


def test_symmetric_unsigned_malformed_and_oversized_tokens_fail_closed(token_factory):
    verifier = mcp_auth.FridgeTokenVerifier()
    secret = secrets.token_bytes(32)
    symmetric = jwt.encode({"sub": SUBJECT}, secret, algorithm="HS256", headers={"typ": "at+jwt"})
    unsigned = jwt.encode({"sub": SUBJECT}, key="", algorithm="none", headers={"typ": "at+jwt"})
    for token in (symmetric, unsigned, "not.a.jwt", "", "x" * 16385):
        assert verifier._verify(token) is None


def test_jwks_failure_is_unauthenticated(token_factory, monkeypatch):
    def fail(token):
        raise jwt.PyJWKClientError("Synthetic missing signing key")

    monkeypatch.setattr(mcp_auth, "_jwk_client", lambda url: SimpleNamespace(get_signing_key_from_jwt=fail))
    assert mcp_auth.FridgeTokenVerifier()._verify(token_factory()) is None


def test_scope_intersection_never_expands_the_grant(token_factory, monkeypatch):
    monkeypatch.setattr(settings, "mcp_grants", [{
        **settings.mcp_grants[0], "scopes": ["fridge:read"],
    }])
    verified = mcp_auth.FridgeTokenVerifier()._verify(token_factory(scope="fridge:read fridge:shopping admin"))
    assert verified is not None
    assert verified.scopes == ["fridge:read"]


def test_token_without_write_scope_stays_read_only(token_factory):
    verified = mcp_auth.FridgeTokenVerifier()._verify(token_factory(scope="fridge:read"))
    assert verified is not None
    assert verified.scopes == ["fridge:read"]


def test_grant_revocation_is_checked_on_each_verification(token_factory, monkeypatch):
    token = token_factory()
    verifier = mcp_auth.FridgeTokenVerifier()
    assert verifier._verify(token) is not None
    monkeypatch.setattr(settings, "mcp_grants", [])
    assert verifier._verify(token) is None


def test_deleted_app_user_is_not_recreated(token_factory, isolated_sessions):
    with isolated_sessions() as db:
        db.delete(db.get(models.User, USER_ID))
        db.commit()
    assert mcp_auth.FridgeTokenVerifier()._verify(token_factory()) is None
    with isolated_sessions() as db:
        assert db.get(models.User, USER_ID) is None
        assert db.query(models.User).count() == 1


@pytest.mark.parametrize("client_id", [CLIENT, "", None])
def test_rest_rejects_any_delegated_client_claim(token_factory, client_id):
    token = token_factory(
        headers={"typ": "JWT"}, iss=settings.supabase_issuer,
        aud="authenticated", sub=USER_ID, client_id=client_id,
    )
    with pytest.raises(HTTPException) as exc:
        auth.verify_supabase_jwt(token)
    assert exc.value.status_code == 401


@pytest.mark.parametrize("typ", ["at+jwt", "application/at+jwt"])
def test_rest_rejects_access_token_type_even_without_client_claim(token_factory, typ):
    token = token_factory(
        headers={"typ": typ}, omit=["client_id"], iss=settings.supabase_issuer,
        aud="authenticated", sub=USER_ID,
    )
    with pytest.raises(HTTPException) as exc:
        auth.verify_supabase_jwt(token)
    assert exc.value.status_code == 401


def test_first_party_rest_session_still_works(token_factory):
    token = token_factory(
        headers={"typ": "JWT"}, omit=["client_id"],
        iss=settings.supabase_issuer, aud="authenticated", sub=USER_ID,
    )
    assert auth.verify_supabase_jwt(token).id == USER_ID


def test_rejected_delegated_token_does_not_upsert_rest_user(token_factory, isolated_sessions):
    new_user_id = "33333333-3333-4333-8333-333333333333"
    token = token_factory(
        iss=settings.supabase_issuer, aud="authenticated", sub=new_user_id,
    )
    with isolated_sessions() as db:
        with pytest.raises(HTTPException):
            auth.get_current_user(
                creds=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db=db,
            )
        assert db.get(models.User, new_user_id) is None
