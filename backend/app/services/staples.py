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


def _staple_words(name: str) -> list[str]:
    tokens = _words(name)
    while tokens and tokens[0] in {"freshly", "fresh", "ground", "finely", "coarsely", "chopped", "minced"}:
        tokens.pop(0)
    return tokens


def is_staple(name: str, staples: list[str]) -> bool:
    """Match complete names, allowing known variants of generic salt/pepper.

    A whole-word containment test still confuses bell pepper with pepper and
    peanut butter with butter. Unknown compounds must remain shopping needs.
    """
    ingredient = _staple_words(name)
    if not ingredient:
        return False
    for s in staples or []:
        staple = _staple_words(s)
        if ingredient == staple:
            return True
        variants = {
            "salt": {"sea", "kosher", "table", "fine", "coarse", "iodized"},
            "pepper": {"black", "white"},
        }
        if (len(staple) == 1 and staple[0] in variants and
                ingredient[-1] == staple[0] and
                set(ingredient[:-1]) <= variants[staple[0]]):
            return True
    return False
