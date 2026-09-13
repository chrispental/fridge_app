"""Conservative ingredient identity and quantity allocation shared by every flow.

Unknown quantities or incompatible units require a check; they never prove that a
recipe can be cooked. An inventory lot is allocated only once within a plan.
"""
import re
import unicodedata
from datetime import date

from .staples import is_staple
from .units import normalize_unit, to_base

_SINGULAR = {
    "tomatoes": "tomato", "potatoes": "potato", "leaves": "leaf",
    "loaves": "loaf", "anchovies": "anchovy", "berries": "berry", "cherries": "cherry",
    "strawberries": "strawberry", "blueberries": "blueberry",
}
_PLURALS = set("eggs onions carrots peppers apples lemons limes oranges bananas peas beans lentils chickpeas soybeans nuts groundnuts peanuts almonds walnuts cashews pecans pistachios hazelnuts macadamias crabs lobsters prawns shrimps scallops clams mussels oysters sardines anchovies breasts thighs cloves mushrooms noodles crackers oats".split())
_PREPARATION = set("fresh frozen chopped diced sliced minced grated shredded peeled boneless skinless large medium small".split())
# Explicit equivalents, never a substring match (ham != graham; butter != peanut butter).
_ALIASES = {
    "garbanzo bean": "chickpea", "scallion": "green onion",
    "scallions": "green onion", "spring onion": "green onion",
    "chicken breast": "chicken", "chicken thigh": "chicken",
}


def words(value: str) -> list[str]:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return [_SINGULAR.get(t, t[:-1] if t in _PLURALS else t) for t in tokens]


def ingredient_key(name: str) -> str:
    tokens = words(re.sub(r"\([^)]*\)", "", name or ""))
    key = " ".join(t for t in tokens if t not in _PREPARATION)
    return _ALIASES.get(key, key)


def same_ingredient(a: str, b: str) -> bool:
    key = ingredient_key(a)
    return bool(key and key == ingredient_key(b))


def convert(quantity, from_unit, to_unit):
    source = to_base(quantity, normalize_unit(from_unit))
    target = to_base(1, normalize_unit(to_unit))
    if source is None or target is None or source[0] != target[0]:
        return None
    return source[1] / target[1]


class StockPool:
    def __init__(self, inventory, staples=()):
        self.staples = staples
        self.lots = [
            {"item": i, "quantity": getattr(i, "quantity", None)}
            for i in sorted(inventory, key=lambda i: (getattr(i, "expires_at", None) or date.max, getattr(i, "id", 0) or 0))
        ]

    def allocate(self, name, quantity=None, unit="unknown") -> dict:
        unit = normalize_unit(unit)
        result = {"stock_status": "missing", "in_stock": False, "available_quantity": 0.0,
                  "missing_quantity": quantity, "allocations": []}
        if is_staple(name, self.staples):
            return {**result, "stock_status": "staple", "in_stock": True, "missing_quantity": 0}
        lots = [lot for lot in self.lots if same_ingredient(name, lot["item"].name)]
        unknown = False
        remaining = quantity
        for lot in lots:
            have = lot["quantity"]
            if have is not None and have <= 0:
                continue
            converted = convert(have, getattr(lot["item"], "unit", "unknown"), unit)
            if quantity is None or converted is None:
                unknown = True
                continue
            take = min(remaining, converted)
            if take <= 0:
                continue
            original = convert(take, unit, lot["item"].unit)
            lot["quantity"] = max(0, have - original)
            result["allocations"].append((lot["item"], original))
            result["available_quantity"] += take
            remaining = max(0, remaining - take)
        if quantity is not None and remaining <= 1e-8:
            result.update(stock_status="have", in_stock=True, missing_quantity=0)
        elif unknown:
            result.update(stock_status="check", missing_quantity=None)
        elif result["available_quantity"] > 0:
            result.update(stock_status="partial", missing_quantity=remaining)
        return result


def annotate_ingredients(ingredients, inventory, staples):
    pool = StockPool(inventory, staples)
    annotated = []
    for ing in ingredients:
        stock = pool.allocate(ing.get("name", ""), ing.get("quantity"), ing.get("unit"))
        stock.pop("allocations")
        annotated.append({**ing, **stock})
    return annotated
