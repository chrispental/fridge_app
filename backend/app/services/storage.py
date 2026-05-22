"""Where an inventory item is kept.

A small fixed vocabulary, like `units.py`. The frontend `STORAGE` list in
`frontend/src/api/client.js` must stay in sync with `STORAGE_LOCATIONS` here.
"""

# User-facing storage locations, in display order.
STORAGE_LOCATIONS = ("fridge", "freezer", "pantry", "counter")

# Items that haven't been placed yet.
DEFAULT_STORAGE = "unsorted"

_VALID = set(STORAGE_LOCATIONS) | {DEFAULT_STORAGE}

# Best-guess mapping from the existing food `category` to a storage location.
# Only used to seed a value; the user can always move an item afterwards.
_CATEGORY_TO_STORAGE = {
    "produce": "fridge",
    "dairy": "fridge",
    "meat": "fridge",
    "seafood": "fridge",
    "frozen": "freezer",
    "pantry": "pantry",
    "condiment": "fridge",
    "beverage": "fridge",
    "bakery": "counter",
    "other": "pantry",
}


def normalize_storage(value: str | None) -> str:
    """Map free text to a canonical location, falling back to 'unsorted'."""
    v = (value or "").strip().lower()
    return v if v in _VALID else DEFAULT_STORAGE


def storage_from_category(category: str | None) -> str:
    """Best-guess location from a food category; 'unsorted' if unknown."""
    return _CATEGORY_TO_STORAGE.get((category or "").strip().lower(), DEFAULT_STORAGE)
