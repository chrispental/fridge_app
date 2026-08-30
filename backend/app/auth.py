"""The auth seam: every request resolves to an `AuthUser`, in one of two modes.

* **Local mode** (`SUPABASE_URL` unset — the default): there is no login. Every
  request is the fixed local user (`settings.local_user_id`), which keeps the
  zero-accounts `docker compose up` experience for single-user installs.
* **Cloud mode** (`SUPABASE_URL` set): the request must carry a Supabase Auth access
  token (`Authorization: Bearer ...`). It is verified locally against the project's
  JWKS — no network call per request — and the token's `sub` becomes the user id.

Routers depend on `CurrentUser`; they never branch on the mode themselves.
"""
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .config import DEFAULT_LOCAL_USER_ID, settings
from .database import get_db
from .models import utcnow

__all__ = ["AuthUser", "CurrentUser", "DEFAULT_LOCAL_USER_ID", "get_current_user"]

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)
_UNAUTHENTICATED = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None = None


@lru_cache(maxsize=1)
def _jwk_client() -> jwt.PyJWKClient:
    # Caches keys for 10 minutes and refetches on an unknown `kid` (key rotation).
    return jwt.PyJWKClient(settings.supabase_jwks_url, cache_keys=True, lifespan=600)


def verify_supabase_jwt(token: str) -> AuthUser:
    """Validate a Supabase Auth access token and return its user.

    Only asymmetric algorithms are accepted; projects still on the legacy HS256
    shared secret must enable JWT signing keys in the Supabase dashboard.
    """
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256", "RS256"],
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_issuer,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        logger.info("Rejected token: %s", exc.__class__.__name__)
        raise HTTPException(
            401, f"Invalid token: {exc.__class__.__name__}", headers=_UNAUTHENTICATED
        )
    return AuthUser(id=str(claims["sub"]), email=claims.get("email"))


def _touch_user(db: Session, user: AuthUser) -> None:
    """Create the `users` row on first sight; keep email/last_seen fresh after."""
    row = db.get(models.User, user.id)
    if row is None:
        db.add(models.User(id=user.id, email=user.email))
        try:
            db.commit()
        except IntegrityError:  # two first requests raced; the other one won
            db.rollback()
        return
    row.last_seen_at = utcnow()
    if user.email and row.email != user.email:
        row.email = user.email
    db.commit()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthUser:
    if not settings.auth_enabled:
        user = AuthUser(id=settings.local_user_id)
    else:
        if creds is None or not creds.credentials:
            raise HTTPException(401, "Not authenticated", headers=_UNAUTHENTICATED)
        user = verify_supabase_jwt(creds.credentials)
    _touch_user(db, user)
    return user


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
