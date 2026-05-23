"""Shopping-list aggregation for a meal plan.

Pure functions (no DB, no network) so they're easy to unit-test. Given the plan's
meals, the current inventory, and the user's pantry staples, this splits every
required ingredient into "already have" vs. "to buy" — recomputed live against
inventory each call, so adding a missing item to inventory moves it to "have" on
the next request. Staples are assumed on hand and never appear on either list.
"""
from .staples import is_staple


def _norm(name: str) -> str:
    return (name or "").lower().strip()


def _matches_inventory(name: str, inv_names: list[str]) -> bool:
    """Bidirectional substring match — same rule as meal_engine._annotate_in_stock."""
    nm = _norm(name)
    return bool(nm and any(nm in inv or inv in nm for inv in inv_names if inv))


def build_shopping_list(meals, inventory, staples: list[str]) -> dict:
    """Aggregate plan ingredients into {to_buy, have, staples_assumed}.

    `meals` are objects with a `recipe_json` dict; `inventory` are objects with a
    `name`. Ingredients are merged by (normalized name, unit), summing known
    quantities (a line whose amounts are all unknown keeps quantity = None).
    """
    inv_names = [_norm(i.name) for i in inventory]

    # Merge by (normalized name, unit), preserving first-seen display name + order.
    merged: dict[tuple[str, str], dict] = {}
    for meal in meals:
        ingredients = (getattr(meal, "recipe_json", None) or {}).get("ingredients", [])
        for ing in ingredients:
            name = str(ing.get("name", "")).strip()
            if not name:
                continue
            unit = (ing.get("unit") or "unknown")
            key = (_norm(name), unit)
            row = merged.setdefault(
                key, {"name": name, "unit": unit, "quantity": None}
            )
            qty = ing.get("quantity")
            if qty is not None:
                row["quantity"] = (row["quantity"] or 0) + qty

    to_buy, have = [], []
    for row in merged.values():
        if is_staple(row["name"], staples):
            continue  # assumed on hand — never bought or listed
        item = {"name": row["name"], "quantity": row["quantity"], "unit": row["unit"]}
        (have if _matches_inventory(row["name"], inv_names) else to_buy).append(item)

    # Inform the user what's being assumed on hand (the configured policy).
    staples_assumed = [s.strip() for s in (staples or []) if s and s.strip()]

    return {"to_buy": to_buy, "have": have, "staples_assumed": staples_assumed}


def annotate_recipe(recipe_json: dict, inventory, staples: list[str]) -> dict:
    """Return a copy of `recipe_json` with per-ingredient `in_stock` recomputed live
    against current inventory + staples, and staples / now-in-stock items removed from
    `missing_ingredients`. Keeps a meal card's display consistent with the shopping
    list even when inventory or staples changed after the meal was suggested.
    """
    rj = dict(recipe_json or {})
    inv_names = [_norm(i.name) for i in inventory]

    def on_hand(name: str) -> bool:
        return is_staple(name, staples) or _matches_inventory(name, inv_names)

    rj["ingredients"] = [
        {**ing, "in_stock": on_hand(ing.get("name", ""))}
        for ing in rj.get("ingredients", [])
    ]
    rj["missing_ingredients"] = [
        m for m in rj.get("missing_ingredients", []) if not on_hand(m)
    ]
    return rj
