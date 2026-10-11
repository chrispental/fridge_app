"""Approximate nutrition: parsing from the model and schema.org, the backfill
endpoint, and the insights average."""
from datetime import datetime

import pytest
from fastapi import HTTPException

from app import models
from app.routers import meals
from app.services import meal_engine, nutrition as nutrition_service
from app.services.meal_stats import compute_stats
from app.services.nutrition import parse_nutrition
from app.services.recipe_import import find_recipe_json_ld, recipe_from_json_ld
from conftest import LOCAL_USER


def test_parse_nutrition_tolerates_shapes_and_clamps():
    n = parse_nutrition({"calories": 523.4, "protein_g": "32.26", "carbs_g": 48, "fat_g": None})
    assert (n.calories, n.protein_g, n.carbs_g, n.fat_g, n.source) == (523, 32.3, 48.0, None, "estimate")
    label = parse_nutrition({"calories": "250 calories", "proteinContent": "12 g", "fatContent": "9.5 g"}, source="recipe")
    assert (label.calories, label.protein_g, label.carbs_g, label.fat_g, label.source) == (250, 12.0, None, 9.5, "recipe")
    assert parse_nutrition({"calories": -5, "protein_g": "lots"}) is None
    assert parse_nutrition({"calories": 99999}) is None
    assert parse_nutrition("250 kcal") is None and parse_nutrition(None) is None


def test_suggestions_carry_nutrition_and_survive_without_it():
    raw = {"suggestions": [
        {"title": "Soup", "nutrition": {"calories": 310, "protein_g": 12, "carbs_g": 40, "fat_g": 9}},
        {"title": "Salad"},
    ]}
    out = meal_engine._parse_suggestions(raw)
    assert out[0].nutrition.calories == 310 and out[0].model_dump()["nutrition"]["source"] == "estimate"
    assert out[1].nutrition is None
    assert "nutrition" in meal_engine.SUGGESTION_SCHEMA["properties"]["suggestions"]["items"]["required"]


def test_json_ld_nutrition_is_labelled_from_the_recipe():
    html = '''<script type="application/ld+json">{"@type":"Recipe","name":"Dal","recipeIngredient":["1 cup lentils"],
    "recipeInstructions":"Simmer.","nutrition":{"@type":"NutritionInformation","calories":"320 kcal","proteinContent":"18 g",
    "carbohydrateContent":"50 g","fatContent":"4 g"}}</script>'''
    recipe = recipe_from_json_ld(find_recipe_json_ld(html), "https://example.com/dal")
    assert recipe.nutrition.model_dump() == {"calories": 320, "protein_g": 18.0, "carbs_g": 50.0, "fat_g": 4.0, "per_serving": True, "source": "recipe"}


def test_backfill_endpoint_estimates_once_and_rejects_empty_recipes(db, monkeypatch):
    meal = models.Meal(user_id=LOCAL_USER.id, title="Rice", title_normalized="rice",
                       recipe_json={"servings": 2, "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup", "in_stock": True}], "steps": ["Cook."]})
    empty = models.Meal(user_id=LOCAL_USER.id, title="Mystery", title_normalized="mystery", recipe_json={})
    db.add_all([meal, empty]); db.commit()
    seen = {}
    def fake(**kwargs):
        seen["prompt"] = kwargs["user_content"]
        return {"nutrition": {"calories": 205, "protein_g": 4.2, "carbs_g": 45, "fat_g": 0.4}}
    monkeypatch.setattr(nutrition_service, "call_structured", fake)
    out = meals.estimate_meal_nutrition(meal.id, LOCAL_USER, db)
    assert out.recipe_json["nutrition"]["calories"] == 205 and out.recipe_json["steps"] == ["Cook."]
    assert '"rice"' in seen["prompt"] and "in_stock" not in seen["prompt"]
    with pytest.raises(HTTPException) as exc:
        meals.estimate_meal_nutrition(empty.id, LOCAL_USER, db)
    assert exc.value.status_code == 422
    monkeypatch.setattr(nutrition_service, "call_structured", lambda **k: {"nutrition": {}})
    with pytest.raises(HTTPException) as exc:
        meals.estimate_meal_nutrition(meal.id, LOCAL_USER, db)
    assert exc.value.status_code == 502


def test_stats_average_nutrition_over_cooked_meals_with_estimates():
    from types import SimpleNamespace as NS
    def meal(status, cooked, nutrition):
        return NS(id=1, title="m", status=status, cuisine=None, cooked_at=cooked, suggested_at=datetime(2026, 6, 1),
                  rating=None, feedback_tags=None, recipe_json={"nutrition": nutrition} if nutrition is not None else {})
    rows = [
        meal("cooked", datetime(2026, 6, 2), {"calories": 400, "protein_g": 20, "carbs_g": 50, "fat_g": 10}),
        meal("cooked", datetime(2026, 6, 3), {"calories": 600, "protein_g": 30, "carbs_g": None, "fat_g": 20}),
        meal("cooked", datetime(2026, 6, 4), None),
        meal("suggested", None, {"calories": 9000, "protein_g": 1, "carbs_g": 1, "fat_g": 1}),
    ]
    out = compute_stats(rows, now=datetime(2026, 6, 5))["nutrition"]
    assert out == {"meals": 2, "calories": 500, "protein_g": 25.0, "carbs_g": 50.0, "fat_g": 15.0}
    assert compute_stats([rows[2]], now=datetime(2026, 6, 5))["nutrition"] is None
