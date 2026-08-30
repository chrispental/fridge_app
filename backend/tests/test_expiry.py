"""Tests for expiry heuristics, the use-these-first prompt block, sort preference,
and the expires_at column migration."""
from datetime import date
from types import SimpleNamespace

from app.schemas import MealSuggestion, RecipeIngredient
from app.services.expiry import estimate_expiry, expiring_soon, is_expiring
from app.services.meal_engine import _build_user_prompt, _sort_key

TODAY = date(2026, 7, 2)


def _item(name, expires=None):
    return SimpleNamespace(name=name, expires_at=expires)


def _fake_prefs():
    return SimpleNamespace(
        household_size=2, allergies=[], dietary_restrictions=[], equipment=[],
        max_complexity=3, disliked_ingredients=[], disliked_cuisines=[],
        pantry_staples=["salt"],
    )


# --- estimate_expiry ----------------------------------------------------------
def test_estimate_expiry_known_categories():
    assert estimate_expiry("produce", "fridge", TODAY) == date(2026, 7, 9)
    assert estimate_expiry("dairy", "fridge", TODAY) == date(2026, 7, 12)
    assert estimate_expiry("meat", "fridge", TODAY) == date(2026, 7, 5)
    assert estimate_expiry("seafood", "fridge", TODAY) == date(2026, 7, 4)


def test_estimate_expiry_freezer_overrides_category():
    # Even short-lived categories last months in the freezer.
    assert estimate_expiry("meat", "freezer", TODAY) == date(2026, 9, 30)


def test_estimate_expiry_unknown_is_none():
    assert estimate_expiry("canned goods", "pantry", TODAY) is None
    assert estimate_expiry(None, None, TODAY) is None
    assert estimate_expiry("", "counter", TODAY) is None


def test_estimate_expiry_matches_substring_category():
    # Categories from the vision model are free-ish text; keyword matching applies.
    assert estimate_expiry("fresh produce", "fridge", TODAY) is not None
    assert estimate_expiry("Dairy & Eggs", "fridge", TODAY) is not None


# --- expiring_soon / is_expiring ----------------------------------------------
def test_expiring_soon_window_and_order():
    items = [
        _item("bread", date(2026, 7, 4)),
        _item("milk", date(2026, 7, 3)),
        _item("cheese", date(2026, 7, 20)),  # outside window
        _item("rice", None),                 # untracked
    ]
    hits = expiring_soon(items, within_days=3, today=TODAY)
    assert [i.name for i in hits] == ["milk", "bread"]


def test_expiring_soon_includes_already_expired():
    items = [_item("yogurt", date(2026, 6, 30))]
    assert [i.name for i in expiring_soon(items, today=TODAY)] == ["yogurt"]


def test_is_expiring_boundary_day():
    # Exactly `within_days` out counts; one day past the window doesn't.
    assert is_expiring(_item("x", date(2026, 7, 5)), within_days=3, today=TODAY)
    assert not is_expiring(_item("x", date(2026, 7, 6)), within_days=3, today=TODAY)


def test_none_expiry_never_expiring():
    assert not is_expiring(_item("x", None), today=TODAY)


# --- prompt block ---------------------------------------------------------------
def test_prompt_includes_use_these_first_block():
    expiring = [_item("chicken thighs", date(2026, 7, 4))]
    prompt = _build_user_prompt(
        _fake_prefs(), [], [], None, None, None, expiring=expiring
    )
    assert "USE THESE FIRST" in prompt
    assert "chicken thighs (expires 2026-07-04)" in prompt


def test_prompt_omits_block_when_nothing_expiring():
    prompt = _build_user_prompt(_fake_prefs(), [], [], None, None, None, expiring=[])
    assert "USE THESE FIRST" not in prompt


# --- sort preference -------------------------------------------------------------
def _suggestion(title, ingredient_names, in_stock=True, missing=()):
    return MealSuggestion(
        title=title,
        ingredients=[RecipeIngredient(name=n, in_stock=in_stock) for n in ingredient_names],
        missing_ingredients=list(missing),
    )


def test_sort_prefers_expiring_users_on_ties():
    uses_expiring = _suggestion("Chicken Rice", ["chicken thighs", "rice"])
    no_expiring = _suggestion("Bean Chili", ["beans", "tomato"])
    ranked = sorted(
        [no_expiring, uses_expiring],
        key=lambda s: _sort_key(s, ["chicken thighs"]),
    )
    assert ranked[0].title == "Chicken Rice"


def test_sort_shortfall_still_dominates():
    # A meal needing a shopping trip never outranks a makeable-now meal, even
    # if the former uses expiring items.
    makeable = _suggestion("Bean Chili", ["beans", "tomato"])
    needs_shopping = _suggestion("Chicken Rice", ["chicken thighs"], in_stock=False)
    ranked = sorted(
        [needs_shopping, makeable],
        key=lambda s: _sort_key(s, ["chicken thighs"]),
    )
    assert ranked[0].title == "Bean Chili"
