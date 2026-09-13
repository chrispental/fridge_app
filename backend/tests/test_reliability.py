"""Regression tests for the review's data-integrity and failure cases."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.routers import inventory, meals, plans, shopping
from app.services import meal_engine
from app.services.ingredients import StockPool, same_ingredient
from app.services.plan_jobs import fill_plan
from app.services.shopping_list import annotate_recipe, build_shopping_list
from conftest import LOCAL_USER, OTHER_USER


def item(name, qty=None, unit="unknown"):
    return NS(name=name, quantity=qty, unit=unit)


def recipe(name="rice", qty=4, unit="cup"):
    return {"ingredients": [{"name": name, "quantity": qty, "unit": unit, "in_stock": True}], "steps": ["Cook."]}


@pytest.mark.parametrize("a,b", [("ham", "graham crackers"), ("butter", "peanut butter"), ("milk", "almond milk"), ("chicken", "chicken broth"), ("rice", "cooked rice")])
def test_distinct_ingredients_do_not_share_stock(a, b):
    assert not same_ingredient(a, b)


def test_plural_and_preparation_normalization():
    assert same_ingredient("carrots", "chopped carrot")
    assert same_ingredient("chicken breasts", "chicken")


def test_partial_quantity_is_a_shortfall():
    out = build_shopping_list([NS(recipe_json=recipe())], [item("rice", 1, "cup")], [])
    assert out["to_buy"] == [{"name": "rice", "quantity": 3, "unit": "cup"}]
    assert out["have"] == [{"name": "rice", "quantity": 1, "unit": "cup"}]
    annotated = annotate_recipe(recipe(), [item("rice", 1, "cup")], [])
    assert annotated["ingredients"][0]["stock_status"] == "partial"
    assert not annotated["ingredients"][0]["in_stock"]


def test_inventory_is_only_allocated_once_across_units():
    r = {"ingredients": recipe(qty=.75)["ingredients"] + recipe(qty=4, unit="fl oz")["ingredients"]}
    out = build_shopping_list([NS(recipe_json=r)], [item("rice", 1, "cup")], [])
    assert out["to_buy"] == [{"name": "rice", "quantity": 2, "unit": "fl oz"}]


@pytest.mark.parametrize("stock", [item("rice"), item("rice", 1, "pack")])
def test_unknown_or_incompatible_amounts_require_checking(stock):
    out = build_shopping_list([NS(recipe_json=recipe())], [stock], [])
    assert out["to_buy"] == out["have"] == []
    assert out["check"][0]["quantity"] == 4
    assert not annotate_recipe(recipe(), [stock], [])["ingredients"][0]["in_stock"]


def test_packaging_units_and_zero_stock():
    pool = StockPool([item("beans", 1, "can"), item("rice", 0, "cup")])
    assert pool.allocate("beans", 3, "can")["missing_quantity"] == 2
    assert pool.allocate("rice", 1, "cup")["stock_status"] == "missing"


@pytest.mark.parametrize("allergy,ingredient", [("peanuts", "peanut butter"), ("dairy", "whey"), ("milk", "parmesan"), ("shellfish", "shrimp"), ("tree nuts", "cashews"), ("sesame", "tahini"), ("soy", "tofu"), ("soy", "soybeans"), ("peanuts", "groundnuts"), ("tree nuts", "macadamias"), ("eggs", "mayonnaise")])
def test_allergen_categories_and_aliases(allergy, ingredient):
    suggestion = schemas.MealSuggestion(title="Dinner", ingredients=[schemas.RecipeIngredient(name=ingredient)])
    assert meal_engine._allergen_violation(suggestion, [allergy])


def test_custom_allergy_uses_whole_words():
    assert not meal_engine._allergen_violation(schemas.MealSuggestion(title="Graham crackers"), ["ham"])


def test_confirm_scan_replay_is_safe(db):
    batch = models.ExtractionBatch(user_id=LOCAL_USER.id, image_key="test.jpg", status="pending_review")
    db.add(batch); db.commit()
    payload = schemas.ConfirmExtractionRequest(items=[schemas.InventoryItemCreate(name="Carrots", quantity=2, unit="piece")])
    first = inventory.confirm_extraction(batch.id, payload, LOCAL_USER, db)
    again = inventory.confirm_extraction(batch.id, payload, LOCAL_USER, db)
    assert [i.id for i in first] == [i.id for i in again]
    assert db.query(models.InventoryItem).count() == 1
    assert db.get(models.ExtractionBatch, batch.id).status == "confirmed"
    with pytest.raises(HTTPException) as error:
        inventory.confirm_extraction(batch.id, payload, OTHER_USER, db)
    assert error.value.status_code == 404


def test_failed_scan_cannot_be_confirmed(db):
    batch = models.ExtractionBatch(user_id=LOCAL_USER.id, image_key="test.jpg", status="discarded")
    db.add(batch); db.commit()
    with pytest.raises(HTTPException) as error:
        inventory.confirm_extraction(batch.id, schemas.ConfirmExtractionRequest(items=[]), LOCAL_USER, db)
    assert error.value.status_code == 409


def test_reopening_old_scan_does_not_extend_expiry(db):
    old = datetime(2020, 1, 1)
    batch = models.ExtractionBatch(user_id=LOCAL_USER.id, image_key="test.jpg", created_at=old,
                                  raw_ai_response={"items": [{"name": "milk", "category": "dairy", "storage": "fridge"}]})
    db.add(batch); db.commit()
    result = inventory.get_extraction(batch.id, LOCAL_USER, db)
    assert result.items[0].expires_at < date(2020, 2, 1)


def test_cook_uses_current_stock_and_request_id(db):
    stock = models.InventoryItem(user_id=LOCAL_USER.id, name="rice", quantity=10, unit="cup")
    meal = models.Meal(user_id=LOCAL_USER.id, title="Rice", title_normalized="rice", recipe_json=recipe(qty=2))
    db.add_all([stock, meal]); db.commit()
    payload = schemas.CookRequest(decrement_inventory=True, request_id=uuid4())
    meals.cook_meal(meal.id, payload, LOCAL_USER, db)
    meals.cook_meal(meal.id, payload, LOCAL_USER, db)
    assert db.get(models.InventoryItem, stock.id).quantity == 8
    meals.cook_meal(meal.id, schemas.CookRequest(decrement_inventory=True, request_id=uuid4()), LOCAL_USER, db)
    assert db.get(models.InventoryItem, stock.id).quantity == 6


def test_cook_allocates_multiple_lots_in_expiry_order(db):
    early = models.InventoryItem(user_id=LOCAL_USER.id, name="rice", quantity=1, unit="cup", expires_at=date.today())
    later = models.InventoryItem(user_id=LOCAL_USER.id, name="rice", quantity=3, unit="cup", expires_at=date.today()+timedelta(days=7))
    meal = models.Meal(user_id=LOCAL_USER.id, title="Rice", title_normalized="rice", recipe_json=recipe(qty=2))
    db.add_all([early, later, meal]); db.commit(); early_id=early.id
    meals.cook_meal(meal.id, schemas.CookRequest(decrement_inventory=True), LOCAL_USER, db)
    assert db.get(models.InventoryItem, early_id) is None
    assert db.get(models.InventoryItem, later.id).quantity == 2


def test_generation_filters_duplicate_titles_with_no_repeat_disabled(db, monkeypatch):
    db.add(models.Preferences(user_id=LOCAL_USER.id, no_repeat_days=0)); db.commit()
    monkeypatch.setattr(meal_engine, "_generate", lambda *a, **k: [schemas.MealSuggestion(title="Stew"), schemas.MealSuggestion(title="Stew!")])
    monkeypatch.setattr(meal_engine, "_enrich_with_brave", lambda *a: None)
    assert len(meal_engine.suggest_meals(db, LOCAL_USER.id, count=2)) == 1


@pytest.fixture
def api_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        db.add(models.User(id=LOCAL_USER.id)); db.commit()
    def provide_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = provide_db
    app.dependency_overrides[get_current_user] = lambda: LOCAL_USER
    # Deliberately omit lifespan: the worker is exercised deterministically below.
    client = TestClient(app)
    yield client, sessions
    client.close()
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize("payload", [{"name": "  "}, {"name": "rice", "quantity": -1}])
def test_invalid_inventory_rejected_over_http(api_client, payload):
    client, _ = api_client
    assert client.post("/api/inventory", json=payload).status_code == 422


def test_plan_returns_promptly_and_replays_same_job(api_client):
    client, _ = api_client
    payload = {"count": 3, "request_id": str(uuid4())}
    first = client.post("/api/plans", json=payload)
    assert first.status_code == 202 and first.json()["status"] == "queued"
    assert client.post("/api/plans", json=payload).json()["id"] == first.json()["id"]
    assert client.post("/api/plans", json={"count": 2}).status_code == 409


def test_failed_plan_keeps_slots_and_resumes(api_client, monkeypatch):
    client, sessions = api_client
    plan_id = client.post("/api/plans", json={"count": 3}).json()["id"]
    with sessions() as db:
        plan = db.get(models.MealPlan, plan_id); plan.status="generating"; db.commit()
    monkeypatch.setattr(meal_engine, "_enrich_with_brave", lambda *a: None)
    calls = iter([[schemas.MealSuggestion(title="Tomato soup")], RuntimeError("provider failed")])
    def generate(*a, **k):
        value = next(calls)
        if isinstance(value, Exception): raise value
        return value
    monkeypatch.setattr(meal_engine, "_generate", generate)
    fill_plan(plan_id, sessions)
    state = client.get("/api/plans/current").json()
    assert state["status"] == "failed" and len(state["entries"]) == 1
    assert client.post(f"/api/plans/{plan_id}/resume").json()["status"] == "queued"
    with sessions() as db:
        plan = db.get(models.MealPlan, plan_id); plan.status="generating"; db.commit()
    calls = iter([[schemas.MealSuggestion(title="Chicken tacos")], [schemas.MealSuggestion(title="Spinach omelet")]])
    fill_plan(plan_id, sessions)
    state = client.get("/api/plans/current").json()
    assert state["status"] == "ready"
    assert [e["slot_index"] for e in state["entries"]] == [0, 1, 2]


def test_failed_action_rolls_back_receipt_and_can_retry(db):
    from app.services.actions import claim_action
    _, claimed = claim_action(db, LOCAL_USER.id, 'retry-after-failure')
    assert claimed
    db.rollback()
    assert db.query(models.ActionReceipt).count() == 0
    _, claimed = claim_action(db, LOCAL_USER.id, 'retry-after-failure')
    assert claimed
    db.commit()
    assert claim_action(db, LOCAL_USER.id, 'retry-after-failure')[1] is False


def test_failed_plan_slot_does_not_leave_an_orphan_meal(api_client, monkeypatch):
    from app.services import plan_jobs
    client, sessions = api_client
    plan_id = client.post('/api/plans', json={'count': 2}).json()['id']
    with sessions() as db:
        db.get(models.MealPlan, plan_id).status = 'generating'
        db.commit()
    def fail_after_flush(db, user_id, **kwargs):
        db.add(models.Meal(user_id=user_id, title='Unfinished meal', title_normalized='unfinished meal', recipe_json={}))
        db.flush()
        raise RuntimeError('provider/slot failure')
    monkeypatch.setattr(plan_jobs, 'suggest_meals', fail_after_flush)
    fill_plan(plan_id, sessions)
    with sessions() as db:
        assert db.query(models.Meal).count() == 0
        assert db.query(models.MealPlanEntry).count() == 0
        assert db.get(models.MealPlan, plan_id).status == 'failed'
