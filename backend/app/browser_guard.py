"""Browser protections for local (no-login) mode.

Local mode has no credentials, so the API trusts anything that reaches the port. The
port is bound to 127.0.0.1, but the user's own browser can still be made to reach it
by any web page they have open:

* **Cross-site requests.** A form post or a `no-cors` fetch with no body or a
  multipart body needs no CORS preflight, so it reaches POST endpoints even though
  the page can't read the answer. That is enough to run paid AI and Brave calls
  (`/meals/suggest`, `/inventory/extract`, a plan swap) or change the kitchen.
  Browsers always send `Origin` on such requests, so an unsafe request whose origin
  isn't this app is refused.
* **DNS rebinding.** A page on attacker.example re-resolves its name to 127.0.0.1 and
  then reads the whole API as same-origin. Its requests still carry
  `Host: attacker.example`, so only the hosts the app is served under are accepted.

Cloud mode is left alone: every request carries a bearer token the browser never
attaches by itself, and its public hostname isn't known here.
"""
import json
from urllib.parse import urlsplit

from .config import settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _hostname(value: str) -> str:
    """Host header or origin authority -> bare lowercase hostname (no port/brackets)."""
    try:
        host = urlsplit(f"//{value}").hostname
    except ValueError:
        return ""
    return (host or "").lower()


def _origin_allowed(origin: str) -> bool:
    if origin in settings.cors_origins_list:
        return True
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and _hostname(parts.netloc) in settings.local_allowed_hosts_list


def _reason(scope) -> str | None:
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
    allowed_hosts = settings.local_allowed_hosts_list
    if "*" not in allowed_hosts and _hostname(headers.get("host", "")) not in allowed_hosts:
        return "Unknown host. Add it to LOCAL_ALLOWED_HOSTS to serve the app under it."
    origin = headers.get("origin")
    if scope["method"] not in SAFE_METHODS and origin is not None and not _origin_allowed(origin):
        return "Cross-site request refused."
    return None


class LocalBrowserGuard:
    """Pure ASGI middleware so streaming responses and lifespan pass through untouched."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or settings.auth_enabled:
            return await self.app(scope, receive, send)
        reason = _reason(scope)
        if reason is None:
            return await self.app(scope, receive, send)
        body = json.dumps({"detail": reason}).encode()
        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})
