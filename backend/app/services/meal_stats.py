"""Meal-history statistics for the insights dashboard.

Pure computation over Meal rows (no DB queries) so it's easy to unit-test.
`recipe_json` shapes vary across the app's history — rows gain `delivery_options`
after ordering, `annotate_recipe` rewrites ingredient dicts, and the AI repair
ladder can emit loosely shaped output — so everything here is defensive `.get()`s.
"""
from collections import Counter
from datetime import date, timedelta

from .staples import is_staple


def _week_start(d: date) -> date:
    """Monday of the ISO week containing `d`."""
    return d - timedelta(days=d.weekday())


def compute_stats(meals, staples=None, now=None) -> dict:
    staples = staples or []

    totals = Counter(getattr(m, "status", None) or "suggested" for m in meals)
    cooked_meals = [m for m in meals if getattr(m, "cooked_at", None) is not None]

    # Top-rated: thumbs-up meals, most recently cooked first.
    top_rated = sorted(
        (m for m in meals if getattr(m, "rating", None) == 1),
        key=lambda m: (m.cooked_at or m.suggested_at),
        reverse=True,
    )[:5]

    # Cuisine breakdown of what was actually cooked.
    cuisine_counts = Counter(
        (getattr(m, "cuisine", None) or "Other") for m in cooked_meals
    )

    # Cooks per week over the last 8 ISO weeks (deterministic given `now`).
    today = (now.date() if hasattr(now, "date") else now) or date.today()
    this_week = _week_start(today)
    week_starts = [this_week - timedelta(weeks=i) for i in range(7, -1, -1)]
    per_week = Counter(_week_start(m.cooked_at.date()) for m in cooked_meals)
    cooks_per_week = [
        {"week_start": ws, "count": per_week.get(ws, 0)} for ws in week_starts
    ]

    # Most-used ingredients across cooked meals, staples excluded so salt/pepper
    # don't dominate. Tolerates any recipe_json shape.
    ingredient_counts: Counter = Counter()
    for m in cooked_meals:
        rj = getattr(m, "recipe_json", None)
        if not isinstance(rj, dict):
            continue
        ingredients = rj.get("ingredients")
        if not isinstance(ingredients, list):
            continue
        for ing in ingredients:
            if not isinstance(ing, dict):
                continue
            name = str(ing.get("name") or "").strip().lower()
            if name and not is_staple(name, staples):
                ingredient_counts[name] += 1

    # Feedback tag frequencies across all meals.
    tag_counts: Counter = Counter()
    for m in meals:
        for tag in getattr(m, "feedback_tags", None) or []:
            tag = str(tag).strip()
            if tag:
                tag_counts[tag] += 1

    return {
        "totals": {
            "total": len(meals),
            "suggested": totals.get("suggested", 0),
            "cooked": totals.get("cooked", 0),
            "ordered": totals.get("ordered", 0),
        },
        "top_rated": [
            {"id": m.id, "title": m.title, "cooked_at": m.cooked_at} for m in top_rated
        ],
        "cuisines": [
            {"cuisine": c, "count": n} for c, n in cuisine_counts.most_common(8)
        ],
        "cooks_per_week": cooks_per_week,
        "top_ingredients": [
            {"name": n, "count": c} for n, c in ingredient_counts.most_common(10)
        ],
        "feedback_tags": [
            {"tag": t, "count": c} for t, c in tag_counts.most_common(10)
        ],
    }
