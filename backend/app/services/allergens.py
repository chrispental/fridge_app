"""Additional server-side allergy filtering, not a food-safety guarantee.

The major categories follow FDA's food-allergen guidance. These conservative,
maintained ingredient aliases are intentionally not an exhaustive food database;
compound products and cross-contact still require checking labels.
https://www.fda.gov/food/food-labeling-nutrition/food-allergies-what-you-need-know
"""
from .ingredients import words

_GROUPS = {
    "peanut": ("peanut", "groundnut", "arachis"),
    "milk": ("milk", "dairy", "butter", "cream", "cheese", "yogurt", "yoghurt", "whey", "casein", "caseinate", "ghee", "paneer", "cheddar", "parmesan", "mozzarella", "ricotta", "feta"),
    "egg": ("egg", "albumen", "albumin", "mayonnaise", "meringue"),
    "soy": ("soy", "soya", "soybean", "tofu", "tempeh", "edamame", "miso", "shoyu", "tamari"),
    "sesame": ("sesame", "tahini", "benne", "gingelly"),
    "wheat": ("wheat", "semolina", "durum", "bulgur", "couscous", "seitan", "spelt", "farina", "einkorn"),
    "tree nut": ("tree nut", "almond", "cashew", "walnut", "pecan", "pistachio", "hazelnut", "macadamia", "brazil nut", "pine nut", "marzipan"),
    "shellfish": ("shellfish", "shrimp", "prawn", "crab", "lobster", "crayfish", "crawfish", "scallop", "clam", "mussel", "oyster"),
    "fish": ("fish", "salmon", "tuna", "cod", "haddock", "anchovy", "sardine", "trout", "bonito", "tilapia", "mackerel"),
}
_CATEGORY_ALIASES = {"dairy": "milk", "soya": "soy", "soybean": "soy", "tree nuts": "tree nut", "nuts": "nut", "nut": "nut"}


def _contains(text, phrase):
    return f" {' '.join(words(phrase))} " in text


def violates_allergies(suggestion, allergies):
    text = " " + " ".join(words(" ".join(
        [suggestion.title or ""] + [i.name for i in suggestion.ingredients]
        + list(suggestion.missing_ingredients) + list(suggestion.steps)
    ))) + " "
    for allergy in allergies or []:
        key = " ".join(words(allergy.strip()))
        if not key:
            continue
        key = _CATEGORY_ALIASES.get(key, key)
        terms = (_GROUPS["tree nut"] + _GROUPS["peanut"]) if key == "nut" else _GROUPS.get(key, (key,))
        if any(_contains(text, term) for term in terms):
            return True
    return False
