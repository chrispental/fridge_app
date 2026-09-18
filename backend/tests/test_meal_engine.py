from types import SimpleNamespace

import pytest

from app.schemas import MealSuggestion, RecipeIngredient
from app.services.meal_engine import (
    _allergen_violation,
    _annotate_in_stock,
    _build_user_prompt,
    _is_repeat,
    _parse_suggestions,
    normalize_title,
)


def _fake_prefs():
    return SimpleNamespace(
        household_size=2, allergies=[], dietary_restrictions=[], equipment=[],
        max_complexity=3, disliked_ingredients=[], disliked_cuisines=[],
        pantry_staples=["salt"],
    )


def test_user_prompt_includes_idea():
    prompt = _build_user_prompt(_fake_prefs(), [], [], None, "spicy thai noodles")
    assert "spicy thai noodles" in prompt
    assert "WHAT THE USER WANTS" in prompt


def test_user_prompt_omits_idea_section_when_empty():
    assert "WHAT THE USER WANTS" not in _build_user_prompt(_fake_prefs(), [], [], None, None)
    assert "WHAT THE USER WANTS" not in _build_user_prompt(_fake_prefs(), [], [], None, "   ")


def test_user_prompt_includes_feedback():
    prompt = _build_user_prompt(
        _fake_prefs(), [], [], None, None, ["- Salty Stew: disliked; too salty"]
    )
    assert "PAST FEEDBACK" in prompt
    assert "too salty" in prompt


def test_user_prompt_omits_feedback_when_empty():
    assert "PAST FEEDBACK" not in _build_user_prompt(_fake_prefs(), [], [], None, None, [])


def test_normalize_title():
    assert normalize_title("Chicken Stir-Fry!") == "chicken stir fry"
    assert normalize_title("  Spaghetti   Bolognese  ") == "spaghetti bolognese"


def test_repeat_exact_after_normalization():
    assert _is_repeat("Chicken Stir-Fry", [normalize_title("chicken stir fry")])


def test_repeat_fuzzy():
    # Minor spelling variation should still count as a repeat.
    assert _is_repeat("Spaghetti Bolognese", [normalize_title("Spaghetti Bolognaise")])


def test_not_a_repeat():
    assert not _is_repeat("Beef Tacos", [normalize_title("Chicken Curry")])


def test_repeat_empty_history():
    assert not _is_repeat("Anything", [])


def test_allergen_violation_detected():
    suggestion = MealSuggestion(
        title="Peanut Noodles",
        ingredients=[RecipeIngredient(name="peanuts"), RecipeIngredient(name="noodles")],
    )
    assert _allergen_violation(suggestion, ["peanut"])


def test_allergen_no_violation():
    suggestion = MealSuggestion(
        title="Veg Stir Fry",
        ingredients=[RecipeIngredient(name="broccoli")],
    )
    assert not _allergen_violation(suggestion, ["shellfish"])
    assert not _allergen_violation(suggestion, [])


def test_parse_suggestions():
    raw = {
        "suggestions": [
            {
                "title": "Omelette",
                "cuisine": "French",
                "complexity": 2,
                "steps": ["Crack eggs", "Cook"],
                "ingredients": [{"name": "eggs", "quantity": 3, "unit": "piece"}],
                "missing_ingredients": ["chives"],
            },
            {"title": "", "ingredients": []},  # dropped: no title
        ]
    }
    out = _parse_suggestions(raw)
    assert len(out) == 1
    assert out[0].title == "Omelette"
    assert out[0].ingredients[0].name == "eggs"
    assert out[0].steps == ["Crack eggs", "Cook"]


def test_parse_suggestions_clamps_complexity():
    raw = {"suggestions": [{"title": "X", "complexity": 99}]}
    assert _parse_suggestions(raw)[0].complexity == 5


class _FakeItem:
    def __init__(self, name):
        self.name = name


def test_annotate_in_stock():
    suggestion = MealSuggestion(
        title="Cheese Toast",
        ingredients=[
            RecipeIngredient(name="Cheddar Cheese"),
            RecipeIngredient(name="truffle oil"),
        ],
    )
    _annotate_in_stock(
        suggestion, [_FakeItem("cheddar cheese"), _FakeItem("bread")], staples=[]
    )
    assert suggestion.ingredients[0].stock_status == "check"
    assert suggestion.ingredients[0].in_stock is False
    assert suggestion.ingredients[1].in_stock is False


def test_annotate_in_stock_counts_staples():
    suggestion = MealSuggestion(
        title="Seasoned Eggs",
        ingredients=[RecipeIngredient(name="eggs"), RecipeIngredient(name="salt")],
    )
    _annotate_in_stock(suggestion, [_FakeItem("eggs")], staples=["salt", "pepper"])
    assert suggestion.ingredients[0].stock_status == "check"  # amount unknown
    assert suggestion.ingredients[1].in_stock is True  # staple, assumed on hand


def test_serving_override_regenerates_entire_recipe(monkeypatch):
    from app.services import meal_engine
    prompts = []
    responses = iter([
        {"suggestions": [{"title": "Rice", "servings": 2, "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}], "steps": ["Cook 1 cup rice."]}]},
        {"suggestions": [{"title": "Rice", "servings": 4, "ingredients": [{"name": "rice", "quantity": 2, "unit": "cup"}], "steps": ["Cook 2 cups rice."]}]},
    ])
    def generate(**kwargs):
        prompts.append(kwargs["user_content"])
        return next(responses)
    monkeypatch.setattr(meal_engine, "call_structured", generate)
    prefs = _fake_prefs()
    result = meal_engine._generate(None, prefs, [], [], 1, servings=4)
    assert len(prompts) == 2
    assert "Requested servings for each recipe: 4" in prompts[0]
    assert result[0].servings == 4
    assert result[0].ingredients[0].quantity == 2
    assert result[0].steps == ["Cook 2 cups rice."]
    assert prefs.household_size == 2


def test_servings_default_to_household(monkeypatch):
    from app.services import meal_engine
    def generate(**kwargs):
        assert "Requested servings for each recipe: 2" in kwargs["user_content"]
        return {"suggestions": [{"title": "Soup", "servings": 2}]}
    monkeypatch.setattr(meal_engine, "call_structured", generate)
    assert meal_engine._generate(None, _fake_prefs(), [], [], 1)[0].servings == 2


@pytest.mark.parametrize("returned_servings", [1, None, "two", 2.5, True, 0, 21])
def test_wrong_servings_fail_instead_of_relabeling(monkeypatch, returned_servings):
    from app.services import meal_engine
    monkeypatch.setattr(meal_engine, "call_structured", lambda **kw: {"suggestions": [{"title": "Soup", "servings": returned_servings}]})
    with pytest.raises(RuntimeError, match="requested servings"):
        meal_engine._generate(None, _fake_prefs(), [], [], 1)


@pytest.mark.parametrize("servings", [0, -1, 21, 1.5])
def test_invalid_serving_requests(servings):
    from app.schemas import SuggestRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SuggestRequest(servings=servings)


def test_enrichment_keeps_recipe_links_without_unverified_photos(monkeypatch):
    from app.services import meal_engine
    monkeypatch.setattr(meal_engine.brave_search, "search_image", lambda *a: pytest.fail("Must not fetch an unrelated photo"))
    monkeypatch.setattr(meal_engine.brave_search, "search_web", lambda *a, **k: [{"title": "Soup recipe", "url": "https://example.com/soup"}])
    suggestion = MealSuggestion(title="Soup")
    meal_engine._enrich_with_brave(suggestion)
    assert suggestion.image_url is None
    assert suggestion.source.url == "https://example.com/soup"
