"""Shelf-life heuristics and expiring-soon selection.

Pure functions (no DB, no network). Expiry is never AI-estimated — vision can't
read date stamps and shelf life varies too much. Instead `estimate_expiry` gives
a rough category/storage-based prefill that the user reviews before anything is
persisted (same safeguard as AI quantity estimates), and manual entry is easy.
"""
from datetime import date, timedelta

# Rough shelf life in days by (category keyword). Freezer storage overrides to a
# long horizon; pantry/counter goods generally aren't tracked unless matched here.
_CATEGORY_DAYS = {
    "produce": 7,
    "vegetable": 7,
    "fruit": 7,
    "herb": 5,
    "dairy": 10,
    "cheese": 14,
    "egg": 21,
    "meat": 3,
    "poultry": 3,
    "seafood": 2,
    "fish": 2,
    "deli": 5,
    "bakery": 4,
    "bread": 4,
    "leftover": 4,
    "frozen": 90,
}

_FREEZER_DAYS = 90


def estimate_expiry(category: str | None, storage: str | None, today: date | None = None) -> date | None:
    """Best-effort expiry date from category + storage; None when unknown."""
    today = today or date.today()
    if (storage or "").lower() == "freezer":
        return today + timedelta(days=_FREEZER_DAYS)
    cat = (category or "").lower()
    for keyword, days in _CATEGORY_DAYS.items():
        if keyword in cat:
            return today + timedelta(days=days)
    return None


def is_expiring(item, within_days: int = 3, today: date | None = None) -> bool:
    """True if the item expires within `within_days` (including already expired)."""
    expires = getattr(item, "expires_at", None)
    if expires is None:
        return False
    today = today or date.today()
    return expires <= today + timedelta(days=within_days)


def expiring_soon(items, within_days: int = 3, today: date | None = None) -> list:
    """Items expiring within the window, soonest first."""
    today = today or date.today()
    hits = [i for i in items if is_expiring(i, within_days, today)]
    hits.sort(key=lambda i: i.expires_at)
    return hits
