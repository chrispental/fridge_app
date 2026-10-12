"""MCP domain/approval regressions. No network or paid AI calls.

TEST_DATABASE_URL optionally runs the concurrent import against the disposable
PostgreSQL database used by the migration CI job. Only its synthetic user rows
are removed; never configure it to point at a real kitchen.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.migrations import run_migrations
from app.models import utcnow
from app.routers import mcp_approvals, shopping
from app.services import mcp_tools as service
from conftest import LOCAL_USER, OTHER_USER

CLIENT = "assistant-client"
BASE_URL = "https://fridge.example"


def make_plan(db, *, user_id=LOCAL_USER.id, status="ready", ingredients=None):
    ingredients = ingredients if ingredients is not None else [{"name": "rice", "quantity": 4, "unit": "cup"}]
    meal = models.Meal(user_id=user_id, title="Rice dinner", title_normalized="rice dinner",
                       recipe_json={"ingredients": ingredients, "steps": ["Cook the rice."]}, status="suggested")
    plan = models.MealPlan(user_id=user_id, status=status)
    plan.entries = [models.MealPlanEntry(slot_index=0, meal=meal)]
    db.add(plan)
    db.commit()
    return plan.id


def preview(db, plan_id=None, *, user_id=LOCAL_USER.id, client_id=CLIENT):
    return service.preview_plan_shopping(db, user_id, client_id,
                                         approval_base_url=BASE_URL, plan_id=plan_id)


def approved(db, plan_id=None):
    result = preview(db, plan_id)
    service.approve_shopping(db, LOCAL_USER.id, result["approval_id"])
    return result["approval_id"]


def execute(db, approval_id, *, user_id=LOCAL_USER.id, client_id=CLIENT):
    return service.import_approved_plan_shopping(db, user_id, client_id, approval_id=approval_id)


def assert_error(code, function, *args, **kwargs):
    with pytest.raises(HTTPException) as error:
        function(*args, **kwargs)
    assert error.value.status_code == code


def test_reads_scope_paginate_and_never_create_preferences(db):
    db.add_all([
        models.InventoryItem(user_id=LOCAL_USER.id, name="rice", quantity=1, unit="cup"),
        models.InventoryItem(user_id=LOCAL_USER.id, name="beans", quantity=None),
        models.InventoryItem(user_id=OTHER_USER.id, name="private stock", quantity=10),
        models.Meal(user_id=LOCAL_USER.id, title="Saved rice", title_normalized="saved rice", status="saved",
                    recipe_json={"ingredients": [{"name": "rice", "quantity": 2, "unit": "cup"}]}),
        models.Meal(user_id=LOCAL_USER.id, title="Favorite beans", title_normalized="favorite beans", favorite=True,
                    recipe_json={"ingredients": [{"name": "beans", "quantity": 2, "unit": "cup"}]}),
        models.Meal(user_id=LOCAL_USER.id, title="Not saved", title_normalized="not saved", recipe_json={}),
        models.Meal(user_id=OTHER_USER.id, title="Private favorite", title_normalized="private favorite",
                    recipe_json={}, favorite=True),
    ])
    db.commit()
    first = service.inventory(db, LOCAL_USER.id, limit=1)
    assert len(first["items"]) == 1 and first["has_more"] is True
    assert service.inventory(db, LOCAL_USER.id, offset=1, limit=1)["items"][0]["name"] == "beans"
    assert service.inventory(db, LOCAL_USER.id, query="RICE")["items"][0]["name"] == "rice"
    assert service.inventory(db, LOCAL_USER.id, query="%")["items"] == []
    found = service.search_recipes(db, LOCAL_USER.id)
    assert {row["title"] for row in found["recipes"]} == {"Saved rice", "Favorite beans"}
    saved = service.search_recipes(db, LOCAL_USER.id, query="rice")["recipes"][0]
    assert saved["recipe"]["ingredients"][0]["stock_status"] == "partial"
    favorite = service.search_recipes(db, LOCAL_USER.id, favorites_only=True)["recipes"]
    assert len(favorite) == 1 and favorite[0]["recipe"]["ingredients"][0]["stock_status"] == "check"
    make_plan(db)
    assert service.current_plan(db, LOCAL_USER.id)["entries"][0]["meal"]["title"] == "Rice dinner"
    assert db.query(models.Preferences).count() == 0
    assert not db.new and not db.dirty


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"query": "x" * 201}, {"limit": True}])
def test_inventory_bounds(db, kwargs):
    assert_error(422, service.inventory, db, LOCAL_USER.id, **kwargs)


def test_recipe_and_plan_bounds_fail_without_partial_approval(db):
    make_plan(db, ingredients=[{"name": f"food {index}", "quantity": 1, "unit": "cup"} for index in range(101)])
    assert_error(422, preview, db)
    assert db.query(models.MCPShoppingApproval).count() == 0
    assert db.query(models.ShoppingListItem).count() == 0


def test_output_bound_is_checked_before_preview_commit(db, monkeypatch):
    make_plan(db)
    monkeypatch.setattr(service, "MAX_BYTES", 300)
    assert_error(422, preview, db)
    assert db.query(models.MCPShoppingApproval).count() == 0


def test_current_plan_does_not_leak_foreign_meal_reference(db):
    plan_id = make_plan(db)
    other_meal = models.Meal(user_id=OTHER_USER.id, title="Secret", title_normalized="secret", recipe_json={})
    db.add(other_meal)
    db.flush()
    db.query(models.MealPlanEntry).filter_by(plan_id=plan_id).one().meal_id = other_meal.id
    db.commit()
    assert_error(404, service.current_plan, db, LOCAL_USER.id)
    assert_error(404, preview, db, plan_id)


def test_preview_only_remaining_meals_and_conservative_stock(db):
    plan_id = make_plan(db, ingredients=[
        {"name": "rice", "quantity": 4, "unit": "cup"},
        {"name": "beans", "quantity": 1, "unit": "cup"},
        {"name": "bell pepper", "quantity": 2, "unit": "piece"},
        {"name": "water", "quantity": 2, "unit": "cup"},
        {"name": "salt", "quantity": 1, "unit": "tsp"},
    ])
    db.add_all([models.InventoryItem(user_id=LOCAL_USER.id, name="rice", quantity=1, unit="cup"),
                models.InventoryItem(user_id=LOCAL_USER.id, name="beans", quantity=None, unit="cup"),
                models.InventoryItem(user_id=LOCAL_USER.id, name="pepper", quantity=1, unit="cup")])
    for index, status in enumerate(("cooked", "ordered"), 1):
        meal = models.Meal(user_id=LOCAL_USER.id, title=status, title_normalized=status, status=status,
                           recipe_json={"ingredients": [{"name": "eggs", "quantity": 6, "unit": "piece"}]})
        db.add(models.MealPlanEntry(plan_id=plan_id, slot_index=index, meal=meal))
    db.commit()
    result = preview(db, plan_id)
    assert result["status"] == "pending"
    assert result["approval_url"] == f"{BASE_URL}/mcp-approvals/{result['approval_id']}"
    assert result["to_buy"] == [{"name": "rice", "quantity": 3, "unit": "cup"},
                                 {"name": "bell pepper", "quantity": 2, "unit": "piece"}]
    assert result["check"] == [{"name": "beans", "quantity": 1, "unit": "cup"}]
    assert len(result["meals"]) == 3
    assert db.query(models.ShoppingListItem).count() == 0
    assert db.query(models.Preferences).count() == 0


def test_human_approval_required_and_client_user_isolation(db):
    make_plan(db)
    request = preview(db)
    key = request["approval_id"]
    assert_error(409, execute, db, key)
    assert_error(404, service.get_shopping_approval, db, OTHER_USER.id, key)
    assert_error(404, service.approve_shopping, db, OTHER_USER.id, key)
    assert_error(404, service.deny_shopping, db, OTHER_USER.id, key)
    assert_error(404, execute, db, key, user_id=OTHER_USER.id)
    assert_error(404, execute, db, key, client_id="another-client")
    assert_error(403, execute, db, key, client_id=None)
    assert_error(404, execute, db, "not-a-uuid")
    # GET never approves; the explicit first-party route does.
    assert mcp_approvals.get_approval(key, LOCAL_USER, db)["status"] == "pending"
    assert mcp_approvals.approve(key, LOCAL_USER, db)["status"] == "approved"
    assert_error(404, execute, db, key, client_id="another-client")
    assert execute(db, key)["status"] == "imported"


def test_preview_reuses_exact_active_request_without_extending_expiry(db):
    make_plan(db)
    first = preview(db)
    second = preview(db)
    assert first["approval_id"] == second["approval_id"]
    assert first["expires_at"] == second["expires_at"]
    assert preview(db, client_id="second-client")["approval_id"] != first["approval_id"]
    service.approve_shopping(db, LOCAL_USER.id, first["approval_id"])
    assert preview(db)["status"] == "approved"
    assert db.query(models.MCPShoppingApproval).count() == 2


def test_active_request_count_is_bounded_per_owner(db):
    make_plan(db)
    for number in range(20):
        preview(db, client_id=f"client-{number}")
    assert_error(429, preview, db, client_id="one-too-many")
    assert db.query(models.MCPShoppingApproval).count() == 20


def test_approval_and_denial_are_idempotent_and_revocable(db):
    make_plan(db)
    key = approved(db)
    first = service.get_shopping_approval(db, LOCAL_USER.id, key)
    second = service.approve_shopping(db, LOCAL_USER.id, key)
    assert second["approved_at"] == first["approved_at"]
    assert service.deny_shopping(db, LOCAL_USER.id, key)["status"] == "rejected"
    assert service.deny_shopping(db, LOCAL_USER.id, key)["status"] == "rejected"
    assert_error(409, execute, db, key)
    assert_error(409, service.approve_shopping, db, LOCAL_USER.id, key)
    assert preview(db)["approval_id"] != key


@pytest.mark.parametrize("human_approved", [False, True])
def test_expired_request_cannot_be_approved_or_executed(db, human_approved):
    make_plan(db)
    key = approved(db) if human_approved else preview(db)["approval_id"]
    db.get(models.MCPShoppingApproval, key).expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert service.get_shopping_approval(db, LOCAL_USER.id, key)["status"] == "expired"
    assert_error(410, service.approve_shopping, db, LOCAL_USER.id, key)
    assert_error(410, execute, db, key)
    assert db.query(models.ShoppingListItem).count() == 0


@pytest.mark.parametrize("change", ["inventory", "recipe", "cooked", "ordered", "staples", "shopping", "delete-plan", "failed-plan"])
@pytest.mark.parametrize("human_approved", [False, True])
def test_changed_sources_or_shopping_are_stale(db, change, human_approved):
    plan_id = make_plan(db)
    key = approved(db, plan_id) if human_approved else preview(db, plan_id)["approval_id"]
    plan = db.get(models.MealPlan, plan_id)
    if change == "inventory":
        db.add(models.InventoryItem(user_id=LOCAL_USER.id, name="rice", quantity=1, unit="cup"))
    elif change == "recipe":
        plan.entries[0].meal.recipe_json = {"ingredients": [{"name": "rice", "quantity": 7, "unit": "cup"}]}
    elif change in ("cooked", "ordered"):
        plan.entries[0].meal.status = change
    elif change == "staples":
        db.add(models.Preferences(user_id=LOCAL_USER.id, pantry_staples=["rice"]))
    elif change == "shopping":
        db.add(models.ShoppingListItem(user_id=LOCAL_USER.id, name="soap", quantity=1, unit="piece"))
    elif change == "delete-plan":
        db.delete(plan)
    else:
        plan.status = "failed"
    db.commit()
    action = execute if human_approved else lambda db, key: service.approve_shopping(db, LOCAL_USER.id, key)
    assert_error(409, action, db, key)
    assert service.get_shopping_approval(db, LOCAL_USER.id, key)["status"] == "stale"
    assert db.query(models.ActionReceipt).count() == 0
    assert db.query(models.ShoppingListItem).filter_by(name="rice").count() == 0


def test_exact_delta_preserves_checked_rows_and_unknown_amounts(db):
    make_plan(db)
    db.add_all([models.ShoppingListItem(user_id=LOCAL_USER.id, name="rice", quantity=2, unit="cup"),
                models.ShoppingListItem(user_id=LOCAL_USER.id, name="rice", quantity=10, unit="cup", checked=True),
                models.ShoppingListItem(user_id=OTHER_USER.id, name="rice", quantity=50, unit="cup")])
    db.commit()
    request = preview(db)
    assert request["changes"] == [{"operation": "update", "item_id": db.query(models.ShoppingListItem).filter_by(
        user_id=LOCAL_USER.id, checked=False).one().id, "name": "rice", "unit": "cup",
        "previous_quantity": 2, "quantity": 6, "added_quantity": 4}]
    service.approve_shopping(db, LOCAL_USER.id, request["approval_id"])
    result = execute(db, request["approval_id"])
    assert len(result["items"]) == 1 and result["items"][0]["quantity"] == 6
    assert db.query(models.ShoppingListItem).filter_by(user_id=LOCAL_USER.id, checked=True).one().quantity == 10
    assert db.query(models.ShoppingListItem).filter_by(user_id=OTHER_USER.id).one().quantity == 50


def test_unknown_missing_amount_stays_unknown(db):
    make_plan(db, ingredients=[{"name": "rice", "quantity": None, "unit": "cup"}])
    request = preview(db)
    assert request["changes"][0]["quantity"] is None
    service.approve_shopping(db, LOCAL_USER.id, request["approval_id"])
    assert execute(db, request["approval_id"])["items"][0]["quantity"] is None


def test_mcp_then_ui_deduplicates_original_plan_import(db):
    plan_id = make_plan(db)
    key = approved(db, plan_id)
    result = execute(db, key)
    assert result["items"][0]["quantity"] == 4
    assert shopping.import_plan(plan_id, LOCAL_USER, db) == []
    assert db.query(models.ShoppingListItem).one().quantity == 4
    assert db.query(models.ActionReceipt).one().action_key == f"shopping:plan:{plan_id}:original"


def test_ui_then_mcp_deduplicates_original_plan_import(db):
    plan_id = make_plan(db)
    assert shopping.import_plan(plan_id, LOCAL_USER, db)[0].quantity == 4
    request = preview(db, plan_id)
    assert request["already_imported"] is True and request["changes"] == []
    service.approve_shopping(db, LOCAL_USER.id, request["approval_id"])
    assert execute(db, request["approval_id"])["status"] == "already_imported"
    assert db.query(models.ShoppingListItem).one().quantity == 4
    assert db.query(models.ActionReceipt).count() == 1


def test_ui_import_between_approval_and_execution_invalidates(db):
    plan_id = make_plan(db)
    key = approved(db, plan_id)
    shopping.import_plan(plan_id, LOCAL_USER, db)
    assert_error(409, execute, db, key)
    assert db.query(models.ShoppingListItem).one().quantity == 4


def test_empty_import_has_stable_result_without_claiming_ui_original_key(db):
    plan_id = make_plan(db, ingredients=[])
    key = approved(db, plan_id)
    first = execute(db, key)
    assert first["items"] == [] and execute(db, key) == first
    assert db.query(models.ActionReceipt).count() == 0
    assert db.query(models.ShoppingListItem).count() == 0


def test_consumed_result_replays_after_expiry_and_later_shopping_changes(db):
    make_plan(db)
    key = approved(db)
    first = execute(db, key)
    db.query(models.ShoppingListItem).one().quantity = 999
    db.get(models.MCPShoppingApproval, key).expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    db.expire_all()
    assert execute(db, key) == first
    assert db.query(models.ShoppingListItem).one().quantity == 999
    assert service.get_shopping_approval(db, LOCAL_USER.id, key)["status"] == "consumed"
    assert service.approve_shopping(db, LOCAL_USER.id, key)["status"] == "consumed"
    assert_error(409, service.deny_shopping, db, LOCAL_USER.id, key)
    assert_error(404, execute, db, key, client_id="different-client")


def test_import_failure_rolls_back_receipt_changes_and_consumption(db, monkeypatch):
    make_plan(db)
    key = approved(db)
    original = service.merge_into_list
    calls = []
    def fail_after_claim(existing, items):
        calls.append(True)
        if len(calls) == 2:  # First call checks the snapshot; second applies it.
            raise RuntimeError("synthetic write failure")
        return original(existing, items)
    monkeypatch.setattr(service, "merge_into_list", fail_after_claim)
    with pytest.raises(RuntimeError, match="synthetic write failure"):
        execute(db, key)
    assert db.query(models.ActionReceipt).count() == 0
    assert db.query(models.ShoppingListItem).count() == 0
    assert db.get(models.MCPShoppingApproval, key).status == "approved"
    monkeypatch.setattr(service, "merge_into_list", original)
    assert execute(db, key)["items"][0]["quantity"] == 4


def test_result_size_failure_rolls_back_the_import(db, monkeypatch):
    make_plan(db)
    key = approved(db)
    original = service._shopping_item
    def oversized(row):
        return {**original(row), "name": "x" * service.MAX_BYTES}
    monkeypatch.setattr(service, "_shopping_item", oversized)
    assert_error(422, execute, db, key)
    assert db.query(models.ShoppingListItem).count() == 0
    assert db.query(models.ActionReceipt).count() == 0
    assert db.get(models.MCPShoppingApproval, key).status == "approved"


def test_postgres_mutation_bounds_lock_and_statement_waits():
    db = Mock(new=[], dirty=[], deleted=[])
    db.in_transaction.return_value = False
    db.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    with service._mutation(db):
        pass
    statements = [str(call.args[0]) for call in db.execute.call_args_list]
    assert statements[0] == "SET LOCAL lock_timeout = '5s'"
    assert statements[1] == "SET LOCAL statement_timeout = '10s'"
    assert statements[2].startswith("LOCK TABLE action_receipts,")
    assert statements[2].endswith("IN SHARE ROW EXCLUSIVE MODE")
    db.commit.assert_called_once()


def test_concurrent_import_is_atomic_and_replay_survives_new_session(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'mcp-concurrency.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    run_migrations(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    user_id = str(uuid4())
    try:
        with sessions() as db:
            db.add(models.User(id=user_id))
            db.commit()
            plan_id = make_plan(db, user_id=user_id)
            request = preview(db, plan_id, user_id=user_id)
            key = request["approval_id"]
            service.approve_shopping(db, user_id, key)
        def run():
            with sessions() as db:
                return execute(db, key, user_id=user_id)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: run(), range(2)))
        assert results[0] == results[1]
        with sessions() as db:
            assert db.query(models.ShoppingListItem).filter_by(user_id=user_id).one().quantity == 4
            assert db.query(models.ActionReceipt).filter_by(user_id=user_id).count() == 1
            assert execute(db, key, user_id=user_id) == results[0]
    finally:
        with sessions() as db:
            plan_ids = db.query(models.MealPlan.id).filter_by(user_id=user_id)
            db.query(models.MealPlanEntry).filter(models.MealPlanEntry.plan_id.in_(plan_ids)).delete(synchronize_session=False)
            for model in (models.MCPShoppingApproval, models.ActionReceipt, models.MealPlan, models.Meal,
                          models.ShoppingListItem, models.InventoryItem, models.Preferences):
                db.query(model).filter_by(user_id=user_id).delete(synchronize_session=False)
            db.query(models.User).filter_by(id=user_id).delete(synchronize_session=False)
            db.commit()
        engine.dispose()
