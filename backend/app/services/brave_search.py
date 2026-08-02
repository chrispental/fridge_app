"""Brave Search client wrapper.

Used to enrich AI meal suggestions with a real food photo and a "view full recipe"
link, to fetch weather snippets for the grill gate, and to find delivery options.

Every public function is **fail-soft**: any error (network, timeout, non-200, a free
key that lacks Image Search scope, or an unexpected response shape) is logged and
turned into an empty result. Callers therefore never have to handle Brave being down —
suggestion/delivery still succeed, just without the enrichment.
"""
import logging
import re

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_client: httpx.Client | None = None

_TAG_RE = re.compile(r"<[^>]+>")
_ZIP_RE = re.compile(r"^\d{5}(?:-\d{4})?$")
_CITY_STATE_RE = re.compile(r"^\s*(.+?),\s*([A-Za-z]{2})\.?\s*$")


def _location_headers(location: str | None) -> dict:
    """Map a free-text location (ZIP or 'City, ST') to Brave X-Loc-* request headers.

    Brave biases results toward these even without lat/long, so a delivery search
    for "10001" returns places that actually serve that area.
    """
    loc = (location or "").strip()
    if not loc:
        return {}
    headers = {"X-Loc-Country": settings.brave_country}
    if _ZIP_RE.match(loc):
        headers["X-Loc-Postal-Code"] = loc
    else:
        m = _CITY_STATE_RE.match(loc)
        if m:
            headers["X-Loc-City"] = m.group(1).strip()
            headers["X-Loc-State"] = m.group(2).upper()
        else:
            headers["X-Loc-City"] = loc
    return headers


def get_client() -> httpx.Client:
    global _client
    if _client is None:
        if not settings.brave_api_key:
            raise RuntimeError(
                "BRAVE_API_KEY is not set — add it to your .env file."
            )
        _client = httpx.Client(
            base_url=settings.brave_base_url,
            timeout=settings.brave_request_timeout,
            headers={
                "X-Subscription-Token": settings.brave_api_key,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )
    return _client


def _strip_html(text: str) -> str:
    """Brave snippets contain <strong> highlight tags — drop them."""
    return _TAG_RE.sub("", text or "").strip()


def search_web(query: str, count: int = 3, location: str | None = None) -> list[dict]:
    """Return up to `count` web results as {title, url, description}; [] on any failure.

    Pass `location` (ZIP or "City, ST") to bias results to that area via Brave's
    X-Loc-* headers — used for delivery lookups so they're geographically relevant.
    """
    try:
        resp = get_client().get(
            "/web/search",
            params={"q": query, "count": count, "country": settings.brave_country},
            headers=_location_headers(location) or None,
        )
        resp.raise_for_status()
        results = (resp.json().get("web") or {}).get("results") or []
        out = []
        for r in results[:count]:
            url = r.get("url")
            if not url:
                continue
            out.append(
                {
                    "title": _strip_html(r.get("title", "")),
                    "url": url,
                    "description": _strip_html(r.get("description", "")),
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001 - fail-soft by design
        logger.warning("Brave web search failed for %r: %s", query, exc)
        return []


def search_image(query: str) -> str | None:
    """Return the first image URL for `query`; None on any failure (incl. no Image scope)."""
    try:
        resp = get_client().get(
            "/images/search",
            params={"q": query, "count": 1, "safesearch": "strict"},
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            return None
        first = results[0]
        thumb = (first.get("thumbnail") or {}).get("src")
        if thumb:
            return thumb
        return (first.get("properties") or {}).get("url")
    except Exception as exc:  # noqa: BLE001 - fail-soft by design
        logger.warning("Brave image search failed for %r: %s", query, exc)
        return None
