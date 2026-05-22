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


def search_web(query: str, count: int = 3) -> list[dict]:
    """Return up to `count` web results as {title, url, description}; [] on any failure."""
    try:
        resp = get_client().get(
            "/web/search",
            params={"q": query, "count": count, "country": settings.brave_country},
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
