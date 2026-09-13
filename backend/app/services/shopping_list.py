"""Shopping-list aggregation for a meal plan.

Pure functions (no DB, no network) so they're easy to unit-test. Given the plan's
meals, the current inventory, and the user's pantry staples, this splits every
required ingredient into "already have" vs. "to buy" — recomputed live against
inventory each call, so adding a missing item to inventory moves it to "have" on
the next request. Staples are assumed on hand and never appear on either list.
"""
from .ingredients import StockPool, annotate_ingredients, ingredient_key, same_ingredient
from .staples import is_staple
from .units import normalize_unit


def _norm(name: str) -> str:
    return ingredient_key(name)


def _matches_inventory(name: str, inv_names: list[str]) -> bool:
    """Canonical ingredient identity, shared with meal suggestions."""
    return any(same_ingredient(name, inv) for inv in inv_names)


def build_shopping_list(meals, inventory, staples: list[str]) -> dict:
    """Aggregate plan ingredients into {to_buy, have, staples_assumed}.

    `meals` are objects with a `recipe_json` dict; `inventory` are objects with a
    `name`. Ingredients are merged by (normalized name, unit), summing known
    quantities (a line whose amounts are all unknown keeps quantity = None).
    """
    merged = {}
    for meal in meals:
        recipe = getattr(meal, "recipe_json", None) or {}
        ingredients = list(recipe.get("ingredients", []))
        covered = {ingredient_key(i.get("name", "")) for i in ingredients}
        ingredients += [{"name": name} for name in recipe.get("missing_ingredients", [])
                        if ingredient_key(name) not in covered]
        for ing in ingredients:
            name = str(ing.get("name", "")).strip()
            if not name:
                continue
            unit = normalize_unit(ing.get("unit"))
            row = merged.setdefault((ingredient_key(name), unit), {
                "name": name, "unit": unit, "quantity": 0, "unknown": False,
            })
            qty = ing.get("quantity")
            if qty is None:
                row["unknown"] = True
            else:
                row["quantity"] += qty

    pool = StockPool(inventory, staples)
    to_buy, have, check = [], [], []
    for row in merged.values():
        quantity = None if row.pop("unknown") else row["quantity"]
        item = {**row, "quantity": quantity}
        stock = pool.allocate(row["name"], quantity, row["unit"])
        status = stock["stock_status"]
        if status == "staple":
            continue
        if stock["available_quantity"] > 0:
            have.append({**item, "quantity": stock["available_quantity"]})
        if status == "check":
            check.append(item)
        elif status in ("partial", "missing"):
            to_buy.append({**item, "quantity": stock["missing_quantity"]})

    return {"to_buy": to_buy, "have": have, "check": check,
            "staples_assumed": [s.strip() for s in (staples or []) if s and s.strip()]}


def merge_into_list(existing_rows, new_items: list[dict]) -> tuple[list, list[dict]]:
    """Merge `new_items` into the standalone shopping list, deduping against
    UNCHECKED rows by (normalized name, unit) — the same key rule as
    `build_shopping_list`. Checked rows are already in the cart; a re-import
    should create a fresh row rather than resurrect them.

    Returns (updated_rows, creates): existing ORM rows whose quantity was summed,
    and plain dicts for rows to create. Pure — the caller persists.
    """
    open_rows = {
        (_norm(r.name), r.unit): r for r in existing_rows if not r.checked
    }
    updated, creates = [], []
    merged_new: dict[tuple[str, str], dict] = {}

    for item in new_items:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        unit = item.get("unit") or "unknown"
        qty = item.get("quantity")
        key = (_norm(name), unit)

        row = open_rows.get(key)
        if row is not None:
            if qty is not None:
                row.quantity = (row.quantity or 0) + qty
                if row not in updated:
                    updated.append(row)
            continue

        new = merged_new.setdefault(
            key,
            {"name": name, "unit": unit, "quantity": None, "source": item.get("source", "manual")},
        )
        if qty is not None:
            new["quantity"] = (new["quantity"] or 0) + qty

    creates.extend(merged_new.values())
    return updated, creates


def missing_for_meal(recipe_json: dict, inventory, staples: list[str]) -> list[dict]:
    """A meal's shopping needs: out-of-stock ingredients (with amounts) plus any
    `missing_ingredients` strings not already covered by an ingredient line.
    Uses `annotate_recipe` so staples and current inventory are respected.
    """
    from types import SimpleNamespace
    return build_shopping_list([SimpleNamespace(recipe_json=recipe_json)], inventory, staples)["to_buy"]


def annotate_recipe(recipe_json: dict, inventory, staples: list[str]) -> dict:
    """Recompute availability and shortfalls from current inventory, not AI flags."""
    rj = dict(recipe_json or {})
    rj["ingredients"] = annotate_ingredients(rj.get("ingredients", []), inventory, staples)
    covered = {ingredient_key(i["name"]) for i in rj["ingredients"]}
    # Keep unstructured extra ingredients, but replace stale AI availability claims.
    extra_pool = StockPool(inventory, staples)
    extras = [m for m in rj.get("missing_ingredients", [])
              if ingredient_key(m) not in covered
              and extra_pool.allocate(m)["stock_status"] == "missing"]
    rj["missing_ingredients"] = list(dict.fromkeys(
        [i["name"] for i in rj["ingredients"] if i["stock_status"] in ("missing", "partial")] + extras
    ))
    return rj
