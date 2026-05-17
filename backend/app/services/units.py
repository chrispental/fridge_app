"""Unit vocabulary, normalization, and best-effort conversion.

US customary units. Deliberately a small fixed enum rather than a full
unit-conversion engine.
"""
from enum import Enum


class Unit(str, Enum):
    TSP = "tsp"
    TBSP = "tbsp"
    FL_OZ = "fl oz"
    CUP = "cup"
    PINT = "pint"
    QUART = "quart"
    GALLON = "gallon"
    OZ = "oz"
    LB = "lb"
    PIECE = "piece"
    DOZEN = "dozen"
    PACK = "pack"
    CAN = "can"
    JAR = "jar"
    BOTTLE = "bottle"
    BUNCH = "bunch"
    UNKNOWN = "unknown"


ALL_UNITS: list[str] = [u.value for u in Unit]

# unit -> (dimension, factor to the dimension's base unit)
# volume base = fluid ounce; mass base = ounce; count base = piece
_TO_BASE: dict[str, tuple[str, float]] = {
    "tsp": ("volume", 1.0 / 6.0),
    "tbsp": ("volume", 0.5),
    "fl oz": ("volume", 1.0),
    "cup": ("volume", 8.0),
    "pint": ("volume", 16.0),
    "quart": ("volume", 32.0),
    "gallon": ("volume", 128.0),
    "oz": ("mass", 1.0),
    "lb": ("mass", 16.0),
    "piece": ("count", 1.0),
    "dozen": ("count", 12.0),
}

_ALIASES: dict[str, str] = {
    "teaspoon": "tsp", "teaspoons": "tsp", "tsps": "tsp", "t": "tsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsps": "tbsp",
    "tbs": "tbsp", "tbl": "tbsp",
    "fluid ounce": "fl oz", "fluid ounces": "fl oz", "floz": "fl oz",
    "fl. oz.": "fl oz", "fl. oz": "fl oz", "fl-oz": "fl oz", "ozfl": "fl oz",
    "cups": "cup", "c": "cup",
    "pints": "pint", "pt": "pint", "pts": "pint",
    "quarts": "quart", "qt": "quart", "qts": "quart",
    "gallons": "gallon", "gal": "gallon", "gals": "gallon",
    "ounce": "oz", "ounces": "oz", "ozs": "oz", "oz.": "oz",
    "pound": "lb", "pounds": "lb", "lbs": "lb", "lb.": "lb", "#": "lb",
    "pieces": "piece", "pcs": "piece", "pc": "piece", "unit": "piece",
    "units": "piece", "count": "piece", "each": "piece", "ea": "piece",
    "item": "piece", "items": "piece", "whole": "piece",
    "doz": "dozen", "dozens": "dozen",
    "cans": "can", "tin": "can", "tins": "can",
    "jars": "jar",
    "bottles": "bottle", "btl": "bottle",
    "packs": "pack", "package": "pack", "packages": "pack",
    "packet": "pack", "packets": "pack", "pkg": "pack", "box": "pack", "bag": "pack",
    "bunches": "bunch",
}


def normalize_unit(unit: str | None) -> str:
    """Map a free-text unit onto the canonical vocabulary; fall back to 'unknown'.

    Metric units (g, ml, ...) are intentionally NOT aliased to US units — that
    would silently mislabel the amount. They normalize to 'unknown' instead.
    """
    if not unit:
        return "unknown"
    u = str(unit).strip().lower()
    u = _ALIASES.get(u, u)
    return u if u in ALL_UNITS else "unknown"


def to_base(quantity: float | None, unit: str) -> tuple[str, float] | None:
    """Return (dimension, base_quantity), or None if the unit is not convertible."""
    if quantity is None:
        return None
    entry = _TO_BASE.get(unit)
    if not entry:
        return None
    dimension, factor = entry
    return dimension, quantity * factor


def try_subtract(
    have_qty: float | None,
    have_unit: str,
    used_qty: float | None,
    used_unit: str,
) -> float | None:
    """Best-effort subtraction of a used amount from a stocked amount.

    Returns the new quantity expressed in `have_unit`, or None when the two
    amounts cannot be reconciled (incompatible / unknown units).
    """
    have = to_base(have_qty, have_unit)
    used = to_base(used_qty, used_unit)
    if not have or not used or have[0] != used[0]:
        return None
    remaining_base = have[1] - used[1]
    _, have_factor = _TO_BASE[have_unit]
    return max(0.0, remaining_base / have_factor)
