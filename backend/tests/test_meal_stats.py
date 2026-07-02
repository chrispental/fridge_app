"""Tests for the insights stats computation, including malformed recipe_json."""
from datetime import datetime
from types import SimpleNamespace

from app.services.meal_stats import compute_stats


def _meal(
    id=1,
    title="Meal",
    status="suggested",
    cuisine=None,
    cooked_at=None,
    suggested_at=None,
    rating=None,
    feedback_tags=None,
    recipe_json=None,
):
    return SimpleNamespace(
        id=id,
        title=title,
        status=status,
        cuisine=cuisine,
        cooked_at=cooked_at,
        suggested_at=suggested_at or datetime(2026, 6, 1),
        rating=rating,
        feedback_tags=feedback_tags,
        recipe_json=recipe_json,
    )


NOW = datetime(2026, 7, 2, 12, 0)


def test_totals_by_status():
    meals = [
        _meal(1, status="suggested"),
        _meal(2, status="cooked", cooked_at=datetime(2026, 7, 1)),
        _meal(3, status="cooked", cooked_at=datetime(2026, 6, 30)),
        _meal(4, status="ordered"),
    ]
    totals = compute_stats(meals, now=NOW)["totals"]
    assert totals == {"total": 4, "suggested": 1, "cooked": 2, "ordered": 1}


def test_empty_history():
    stats = compute_stats([], now=NOW)
    assert stats["totals"]["total"] == 0
    assert stats["top_rated"] == []
    assert stats["cuisines"] == []
    assert stats["top_ingredients"] == []
    assert len(stats["cooks_per_week"]) == 8
    assert all(w["count"] == 0 for w in stats["cooks_per_week"])


def test_top_rated_recent_first_capped_at_five():
    meals = [
        _meal(i, title=f"M{i}", rating=1, status="cooked", cooked_at=datetime(2026, 6, i))
        for i in range(1, 8)
    ] + [_meal(99, title="Meh", rating=-1, status="cooked", cooked_at=datetime(2026, 6, 20))]
    top = compute_stats(meals, now=NOW)["top_rated"]
    assert len(top) == 5
    assert top[0]["title"] == "M7"  # most recently cooked first
    assert all(t["title"] != "Meh" for t in top)


def test_cuisines_only_cooked_and_none_bucketed():
    meals = [
        _meal(1, cuisine="thai", status="cooked", cooked_at=datetime(2026, 7, 1)),
        _meal(2, cuisine="thai", status="cooked", cooked_at=datetime(2026, 7, 1)),
        _meal(3, cuisine=None, status="cooked", cooked_at=datetime(2026, 7, 1)),
        _meal(4, cuisine="mexican", status="suggested"),  # not cooked — excluded
    ]
    cuisines = {c["cuisine"]: c["count"] for c in compute_stats(meals, now=NOW)["cuisines"]}
    assert cuisines == {"thai": 2, "Other": 1}


def test_cooks_per_week_buckets_with_injected_now():
    meals = [
        _meal(1, status="cooked", cooked_at=datetime(2026, 6, 29)),  # Mon this week
        _meal(2, status="cooked", cooked_at=datetime(2026, 7, 1)),   # Wed this week
        _meal(3, status="cooked", cooked_at=datetime(2026, 6, 23)),  # last week
    ]
    weeks = compute_stats(meals, now=NOW)["cooks_per_week"]
    assert len(weeks) == 8
    assert weeks[-1]["week_start"].isoformat() == "2026-06-29"
    assert weeks[-1]["count"] == 2
    assert weeks[-2]["count"] == 1


def test_top_ingredients_excludes_staples():
    rj = {
        "ingredients": [
            {"name": "Chicken", "quantity": 1},
            {"name": "salt"},
            {"name": "rice"},
        ]
    }
    meals = [
        _meal(1, status="cooked", cooked_at=datetime(2026, 7, 1), recipe_json=rj),
        _meal(2, status="cooked", cooked_at=datetime(2026, 6, 30), recipe_json=rj),
    ]
    top = compute_stats(meals, staples=["salt"], now=NOW)["top_ingredients"]
    names = {t["name"]: t["count"] for t in top}
    assert names == {"chicken": 2, "rice": 2}


def test_malformed_recipe_json_never_crashes():
    meals = [
        _meal(1, status="cooked", cooked_at=datetime(2026, 7, 1), recipe_json=None),
        _meal(2, status="cooked", cooked_at=datetime(2026, 7, 1), recipe_json={}),
        _meal(3, status="cooked", cooked_at=datetime(2026, 7, 1), recipe_json={"ingredients": "oops"}),
        _meal(4, status="cooked", cooked_at=datetime(2026, 7, 1),
              recipe_json={"ingredients": [{"quantity": 2}, "junk", {"name": ""}]}),
        _meal(5, status="cooked", cooked_at=datetime(2026, 7, 1),
              recipe_json={"ingredients": [{"name": "kale"}], "delivery_options": [{"url": "x"}]}),
    ]
    stats = compute_stats(meals, now=NOW)
    assert stats["top_ingredients"] == [{"name": "kale", "count": 1}]


def test_feedback_tags_counted_and_none_tolerated():
    meals = [
        _meal(1, feedback_tags=["Too salty", "Too slow"]),
        _meal(2, feedback_tags=["Too salty"]),
        _meal(3, feedback_tags=None),
    ]
    tags = {t["tag"]: t["count"] for t in compute_stats(meals, now=NOW)["feedback_tags"]}
    assert tags == {"Too salty": 2, "Too slow": 1}
