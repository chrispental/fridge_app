"""Weather lookup for the grilling gate.

Brave has no dedicated weather endpoint, so we web-search the forecast and keyword-scan
the snippets for precipitation. "Winter" is derived deterministically from the date
(northern hemisphere) rather than from Brave, so it's never fragile.

This is a *soft convenience* gate, not a safety rule like allergens, so it **fails open**:
if Brave is down or the snippet is ambiguous we assume it's not raining (grill allowed).
The grill exclusion itself is still enforced server-side in the meal engine.
"""
import logging
import re
import time

from ..config import settings
from ..models import utcnow
from . import brave_search

logger = logging.getLogger(__name__)

# Phrases that indicate active precipitation in a forecast snippet.
_RAIN_KEYWORDS = (
    "rain",
    "showers",
    "thunderstorm",
    "drizzle",
    "precipitation",
    "snow",
    "sleet",
    "downpour",
    "wet weather",
)
# Negations like "no rain" / "rain-free" / "0% chance of rain" should NOT trip the scan.
_NEGATION_RE = re.compile(
    r"(?:\bno\b|\bnot\b|without|free of|0%|zero)\s+(?:chance of\s+)?",
)

_WINTER_MONTHS = {12, 1, 2}

# location_lower -> (expiry_epoch, result dict)
_cache: dict[str, tuple[float, dict]] = {}


def is_winter(month: int) -> bool:
    """Northern-hemisphere winter (Dec/Jan/Feb)."""
    return month in _WINTER_MONTHS


def snippet_mentions_rain(text: str) -> bool:
    """True if `text` describes active precipitation, ignoring obvious negations.

    Pure function (no I/O) so it can be unit-tested directly. Brittle by nature —
    that's acceptable because the caller fails open on ambiguity.
    """
    lowered = (text or "").lower()
    # Drop "no rain", "0% chance of rain", etc. before scanning for keywords.
    cleaned = _NEGATION_RE.sub(" __neg__ ", lowered)
    for kw in _RAIN_KEYWORDS:
        for match in re.finditer(re.escape(kw), cleaned):
            # Skip a keyword immediately preceded by a negation marker.
            preceding = cleaned[max(0, match.start() - 12) : match.start()]
            if "__neg__" in preceding:
                continue
            return True
    return False


def _compute(location: str) -> dict:
    winter = is_winter(utcnow().month)
    results = brave_search.search_web(f"weather today {location}", count=3)
    blob = " ".join(f"{r['title']} {r['description']}" for r in results)
    raining = snippet_mentions_rain(blob)

    grill_ok = not winter and not raining
    if winter:
        summary = "winter — grilling not advised"
    elif raining:
        summary = "rain in the forecast — grilling not advised"
    else:
        summary = "clear and mild — good for grilling"

    return {
        "is_raining": raining,
        "season": "winter" if winter else "non-winter",
        "grill_ok": grill_ok,
        "summary": summary,
    }


def get_weather(location: str) -> dict | None:
    """{is_raining, season, grill_ok, summary} for `location`, or None if no location.

    Cached in-memory per location for `settings.weather_cache_ttl` seconds so repeated
    meal suggestions don't re-hit Brave.
    """
    if not location or not location.strip():
        return None
    key = location.strip().lower()
    now = time.time()
    cached = _cache.get(key)
    if cached and now < cached[0]:
        return cached[1]
    result = _compute(location)
    _cache[key] = (now + settings.weather_cache_ttl, result)
    return result
