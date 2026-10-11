"""Adjust-in-place, leftovers on cook, and per-plan serving/date overrides."""
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.routers import meals, plans
from app.services import meal_engine
from app.services.meal_engine import AdjustmentRejected, MealSuggestion, RecipeIngredient
from app.services.plan_jobs import fill_plan
from conftest import LOCAL_USER, OTHER_USER


def _meal(db, title="Chicken Curry", **recipe):
    row = models.Meal(
        user_id=LOCAL_USER.id, title=title, title_normalized=meal_engine.normalize_title(title),
        recipe_json={"title": title, "servings": 2, "cooking_method": "stovetop",
                     "ingredients": [{"name": "chicken", "quantity": 1, "unit": "lb", "in_stock": True}],
                     "steps": ["Cook the chicken."], "missing_ingredients": [],
                     "source": {"title": "Curry", "url": "https://example.com/curry"}, **recipe},
    )
    db.add(row); db.commit(); db.refresh(row)
    return row


def _ai(monkeypatch, suggestion):
    calls = []
    def fake(system_prompt, prompt, target):
        calls.append((system_prompt, prompt, target))
        return [suggestion]
    monkeypatch.setattr(meal_engine, "_request_suggestions", fake)
    monkeypatch.setattr(meal_engine, "_enrich_with_brave", lambda s, avoid_url=None: None)
    return calls


# --- adjust ------------------------------------------------------------------
def test_adjust_rewrites_the_meal_in_place_and_records_the_instruction(db, monkeypatch):
    meal = _meal(db)
    plan = models.MealPlan(user_id=LOCAL_USER.id, entries=[models.MealPlanEntry(slot_index=0, meal=meal)])
    db.add(plan); db.commit()
    calls = _ai(monkeypatch, MealSuggestion(
        title="Chickpea Curry", servings=2, cuisine="Indian",
        ingredients=[RecipeIngredient(name="chickpeas", quantity=1, unit="can")], steps=["Simmer."]))

    out = meal_engine.adjust_meal(db, LOCAL_USER.id, meal, "make it vegetarian")

    assert out.id == meal.id and out.title == "Chickpea Curry" and out.cuisine == "Indian"
    assert out.recipe_json["adjustments"] == ["make it vegetarian"]
    assert out.recipe_json["ingredients"][0]["name"] == "chickpeas"
    assert db.get(models.MealPlanEntry, plan.entries[0].id).meal.title == "Chickpea Curry"
    system_prompt, prompt, target = calls[0]
    assert "wants it changed" in system_prompt
    assert "ADJUSTMENT REQUESTED: make it vegetarian" in prompt and '"Chicken Curry"' in prompt
    assert target == 2  # the recipe's own serving count, not household size

    # A second adjustment builds on the first and keeps the history.
    _ai(monkeypatch, MealSuggestion(title="Quick Chickpea Curry", servings=2, steps=["Simmer briefly."]))
    out = meal_engine.adjust_meal(db, LOCAL_USER.id, out, "faster")
    assert out.recipe_json["adjustments"] == ["make it vegetarian", "faster"]


def test_adjust_keeps_the_recipe_link_when_the_dish_stays_the_same(db, monkeypatch):
    meal = _meal(db)
    _ai(monkeypatch, MealSuggestion(title="Chicken Curry", servings=2, steps=["Add chili."]))
    out = meal_engine.adjust_meal(db, LOCAL_USER.id, meal, "spicier")
    assert out.recipe_json["source"]["url"] == "https://example.com/curry"


def test_adjust_never_introduces_an_allergen(db, monkeypatch):
    db.add(models.Preferences(user_id=LOCAL_USER.id, allergies=["peanut"])); db.commit()
    meal = _meal(db)
    _ai(monkeypatch, MealSuggestion(title="Peanut Chicken Curry", servings=2,
                                    ingredients=[RecipeIngredient(name="peanuts")]))
    with pytest.raises(AdjustmentRejected):
        meal_engine.adjust_meal(db, LOCAL_USER.id, meal, "add peanuts")
    db.refresh(meal)
    assert meal.title == "Chicken Curry" and "adjustments" not in meal.recipe_json


def test_adjust_route_refuses_cooked_meals_and_other_users(db, monkeypatch):
    meal = _meal(db)
    with pytest.raises(HTTPException) as exc:
        meals.adjust(meal.id, schemas.AdjustRequest(instruction="faster"), OTHER_USER, db)
    assert exc.value.status_code == 404
    meal.status = "cooked"; db.commit()
    with pytest.raises(HTTPException) as exc:
        meals.adjust(meal.id, schemas.AdjustRequest(instruction="faster"), LOCAL_USER, db)
    assert exc.value.status_code == 409


def test_adjust_route_maps_rejections_to_422(db, monkeypatch):
    meal = _meal(db)
    def reject(*a, **k):
        raise AdjustmentRejected("nope")
    monkeypatch.setattr(meals, "adjust_meal", reject)
    with pytest.raises(HTTPException) as exc:
        meals.adjust(meal.id, schemas.AdjustRequest(instruction="add peanuts"), LOCAL_USER, db)
    assert exc.value.status_code == 422


# --- leftovers ---------------------------------------------------------------
def test_cook_can_save_leftovers_once_per_request(db):
    meal = _meal(db)
    payload = schemas.CookRequest(decrement_inventory=False, save_leftovers=True, request_id=uuid4())
    meals.cook_meal(meal.id, payload, LOCAL_USER, db)
    meals.cook_meal(meal.id, payload, LOCAL_USER, db)  # replay after a network failure
    rows = db.query(models.InventoryItem).filter_by(user_id=LOCAL_USER.id).all()
    assert [(r.name, r.category, r.storage, r.source, r.quantity) for r in rows] == [
        ("leftover chicken curry", "leftover", "fridge", "leftover", None)]
    assert rows[0].expires_at == date.today() + timedelta(days=4)


def test_cook_without_leftovers_adds_nothing(db):
    meal = _meal(db)
    meals.cook_meal(meal.id, schemas.CookRequest(decrement_inventory=False), LOCAL_USER, db)
    assert db.query(models.InventoryItem).count() == 0


# --- plan overrides ------------------------------------------------------------
def test_plan_overrides_flow_into_each_generated_slot(db, monkeypatch):
    seen = []
    def fake_suggest(db_, user_id, count=1, idea=None, *, commit=True, exclude_titles=None, servings=None):
        seen.append(servings)
        m = models.Meal(user_id=user_id, title=f"Meal {len(seen)}", title_normalized=f"meal {len(seen)}", recipe_json={})
        db_.add(m); db_.flush()
        return [m]
    monkeypatch.setattr("app.services.plan_jobs.suggest_meals", fake_suggest)
    monkeypatch.setattr(meal_engine, "suggest_meals", fake_suggest)

    out = plans.create(schemas.CreatePlanRequest(count=2, servings=6, start_date=date(2026, 10, 12)), LOCAL_USER, db)
    assert (out.servings, out.start_date, out.status) == (6, date(2026, 10, 12), "queued")
    plan = db.get(models.MealPlan, out.id)
    plan.status = "generating"; db.commit()
    fill_plan(plan.id, sessions=lambda: db)
    assert seen == [6, 6]

    # Swapping a slot keeps the plan's serving count too.
    db.expire_all()
    entry = db.get(models.MealPlan, out.id).entries[0]
    meal_engine.swap_slot(db, LOCAL_USER.id, entry)
    assert seen[-1] == 6
    assert plans.current(LOCAL_USER, db).servings == 6


def test_plan_without_overrides_uses_household_size(db, monkeypatch):
    seen = []
    def fake_suggest(db_, user_id, count=1, idea=None, *, commit=True, exclude_titles=None, servings=None):
        seen.append(servings)
        m = models.Meal(user_id=user_id, title="Meal", title_normalized="meal", recipe_json={})
        db_.add(m); db_.flush()
        return [m]
    monkeypatch.setattr("app.services.plan_jobs.suggest_meals", fake_suggest)
    out = plans.create(schemas.CreatePlanRequest(count=1), LOCAL_USER, db)
    assert out.servings is None and out.start_date is None
    db.get(models.MealPlan, out.id).status = "generating"; db.commit()
    fill_plan(out.id, sessions=lambda: db)
    assert seen == [None]
