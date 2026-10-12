"""Dedicated OAuth resource-server boundary; never accepts ordinary app tokens."""
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit
from uuid import UUID

import anyio
import jwt
from fastmcp.server.auth import AccessToken, RemoteAuthProvider, TokenVerifier

from .config import settings
from .database import SessionLocal
from .models import User

READ_SCOPE = "fridge:read"
WRITE_SCOPE = "fridge:shopping"
SCOPES = {READ_SCOPE, WRITE_SCOPE}


@dataclass(frozen=True)
class Grant:
    subject: str
    client_id: str
    user_id: str
    scopes: frozenset[str]


def validated_grants() -> dict[tuple[str, str], Grant]:
    """Explicit administrator mapping, never infer that two issuers share users."""
    grants = {}
    if not settings.mcp_grants or len(settings.mcp_grants) > 1000:
        raise ValueError("MCP requires 1–1000 explicit subject/client grants")
    for row in settings.mcp_grants:
        if set(row) != {"subject", "client_id", "user_id", "scopes"}:
            raise ValueError("Invalid MCP grant fields")
        subject, client, user = row["subject"], row["client_id"], row["user_id"]
        scopes = row["scopes"]
        if not all(isinstance(v, str) and 0 < len(v) <= 200 for v in (subject, client, user)):
            raise ValueError("Invalid MCP grant identity")
        UUID(user)
        if user == settings.local_user_id:
            raise ValueError("MCP cannot access the unauthenticated local user")
        if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
            raise ValueError("Invalid MCP grant scopes")
        if READ_SCOPE not in scopes or not set(scopes) <= SCOPES:
            raise ValueError("MCP grant must include fridge:read and only supported scopes")
        key = (subject, client)
        if key in grants:
            raise ValueError("Duplicate MCP subject/client grant")
        grants[key] = Grant(subject, client, user, frozenset(scopes))
    return grants


def validate_configuration() -> None:
    if not settings.auth_enabled:
        raise ValueError("MCP requires cloud authentication; local mode is never exposed")
    for value in (settings.mcp_resource_url, settings.mcp_issuer_url, settings.mcp_jwks_url):
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("MCP URLs must be absolute HTTPS URLs without credentials, query or fragment")
    if urlsplit(settings.mcp_resource_url).path != "/mcp":
        raise ValueError("MCP_RESOURCE_URL must end in /mcp (without trailing slash)")
    if settings.mcp_issuer_url == settings.supabase_issuer:
        raise ValueError("Use a dedicated MCP issuer; ordinary Supabase OAuth scopes are insufficient")
    validated_grants()


@lru_cache(maxsize=1)
def _jwk_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=False, lifespan=300, timeout=5)


class FridgeTokenVerifier(TokenVerifier):
    def __init__(self):
        super().__init__(required_scopes=[READ_SCOPE])

    async def verify_token(self, token: str) -> AccessToken | None:
        # JWKS and SQLAlchemy are synchronous; do not block the ASGI event loop.
        return await anyio.to_thread.run_sync(self._verify, token)

    def _verify(self, token: str) -> AccessToken | None:
        if len(token) > 16384:
            return None
        try:
            header = jwt.get_unverified_header(token)
            if header.get("typ") not in {"at+jwt", "application/at+jwt"} or header.get("alg") not in {"RS256", "ES256"}:
                return None
            key = _jwk_client(settings.mcp_jwks_url).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256", "ES256"],
                audience=settings.mcp_resource_url, issuer=settings.mcp_issuer_url,
                options={"require": ["exp", "iat", "sub", "iss", "aud", "client_id", "scope", "jti"], "strict_aud": True},
            )
            if not all(isinstance(claims[key], str) and claims[key] for key in ("sub", "client_id", "jti")):
                return None
            if (not isinstance(claims["scope"], str)
                    or type(claims["exp"]) is not int or type(claims["iat"]) is not int
                    or not 0 < claims["exp"] - claims["iat"] <= 900):
                return None
            grant = validated_grants().get((claims["sub"], claims["client_id"]))
            if grant is None:
                return None
            scopes = set(claims["scope"].split()) & grant.scopes
            if READ_SCOPE not in scopes:
                return None
            with SessionLocal() as db:
                if db.get(User, grant.user_id) is None:
                    return None
            return AccessToken(
                token=token, client_id=grant.client_id, subject=grant.subject,
                scopes=sorted(scopes), expires_at=claims["exp"], resource=settings.mcp_resource_url,
                claims={"iss": settings.mcp_issuer_url, "app_user_id": grant.user_id},
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            return None


class ResourceBoundRemoteAuthProvider(RemoteAuthProvider):
    """Advertise the external issuer while enforcing the verifier's resource binding."""
    async def verify_token(self, token: str) -> AccessToken | None:
        verified = await super().verify_token(token)
        if verified is None or verified.resource != settings.mcp_resource_url:
            return None
        return verified
