"""Pantry staples — basics assumed always on hand.

Staples (salt, pepper, hot sauce, ...) never need to live in inventory and never
appear on a shopping list. The list is user-editable via Preferences; this module
holds the seed default and the single matcher reused by the meal engine and the
shopping-list builder.
"""
import re

DEFAULT_STAPLES = ["salt", "pepper", "hot sauce"]


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def _contains_seq(haystack: list[str], needle: list[str]) -> bool:
    """True if `needle` appears as a contiguous run of whole words in `haystack`."""
    n, m = len(haystack), len(needle)
    if m == 0 or m > n:
        return False
    return any(haystack[i : i + m] == needle for i in range(n - m + 1))


def is_staple(name: str, staples: list[str]) -> bool:
    """True if `name` is one of the staples, matched on WHOLE WORDS.

    Word matching (not raw substring) is deliberate: a substring rule would treat
    "jalapeno peppers", "bell pepper", or "salted butter" as the staples "pepper"/
    "salt" and silently drop real shopping-list items. Whole-word matching keeps
    "black pepper" / "sea salt" as staples while leaving those compounds alone.
    """
    ingredient = _words(name)
    if not ingredient:
        return False
    for s in staples or []:
        staple = _words(s)
        if staple and (_contains_seq(ingredient, staple) or _contains_seq(staple, ingredient)):
            return True
    return False
