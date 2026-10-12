"""Small, owner-scoped MCP domain surface; no AI/network or preference writes.

Only the first-party approval router calls ``approve_shopping``. MCP callers may
prepare a request and execute an already approved, unchanged snapshot, never
approve it. Text from recipes/inventory is data, not instructions.

The existing UI mutations do not take a common per-kitchen lock. Brief table
locks on Postgres (BEGIN IMMEDIATE on SQLite) therefore protect approval/import
checks from concurrent UI edits, including inserts. Keep this transaction short
and bounded; there are no network calls while it holds locks.
"""
from contextlib import contextmanager
from datetime import timedelta, timezone
from hashlib import sha256
import json
import math
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .. import models
from ..models import utcnow
from .aisles import guess_category
from .shopping_list import annotate_recipe, build_shopping_list, merge_into_list
from .staples import DEFAULT_STAPLES
from .units import normalize_unit

MAX_ROWS = 1000
MAX_PLAN_ENTRIES = 100
MAX_INGREDIENTS = 100
MAX_BYTES = 65536  # Leave room for the MCP JSON-RPC/content envelope.


def _json(value) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False)
    except (ValueError, TypeError):
        raise HTTPException(422, "Stored kitchen data needs correction before using MCP.")


def _bounded(value):
    if len(_json(value).encode("utf-8")) > MAX_BYTES:
        raise HTTPException(422, "Result is too large. Narrow the request or use Fridge Chef directly.")
    return value


def _digest(value) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _iso(value):
    if value is None:
        return None
    if hasattr(value, "hour"):
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


def _text(value, maximum=300) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise HTTPException(422, "Stored kitchen text is too large or invalid for MCP.")
    return value


def _quantity(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                              or not math.isfinite(value) or value < 0):
        raise HTTPException(422, "Stored ingredient amounts need correction before using MCP.")
    return value


def _paging(query: str, limit: int, offset: int, maximum: int):
    if not isinstance(query, str) or len(query) > 200:
        raise HTTPException(422, "Search text must be at most 200 characters.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
        raise HTTPException(422, f"Limit must be between 1 and {maximum}.")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise HTTPException(422, "Offset must be between 0 and 10000.")
    return query.strip().lower()


def _all_bounded(query, maximum=MAX_ROWS):
    rows = query.limit(maximum + 1).all()
    if len(rows) > maximum:
        raise HTTPException(422, "Kitchen data is too large for a safe MCP calculation. Use Fridge Chef directly.")
    return rows


def _stock(db, user_id):
    rows = _all_bounded(db.query(models.InventoryItem).filter_by(user_id=user_id)
                        .order_by(models.InventoryItem.id))
    for row in rows:
        _inventory_item(row)
    return rows


def _staples(db, user_id):
    # Unlike scope.staples_for, a read must not lazily create preferences.
    prefs = db.query(models.Preferences).filter_by(user_id=user_id).one_or_none()
    values = prefs.pantry_staples if prefs is not None else list(DEFAULT_STAPLES)
    if values is None:
        values = []
    if not isinstance(values, list) or len(values) > MAX_INGREDIENTS:
        raise HTTPException(422, "Too many pantry staples for an MCP calculation.")
    return [_text(value) for value in values]


def _inventory_item(row):
    return {"id": row.id, "name": _text(row.name), "quantity": _quantity(row.quantity),
            "unit": _text(row.unit, 50), "category": row.category, "storage": row.storage,
            "expires_at": _iso(row.expires_at)}


def _shopping_item(row):
    return {"id": row.id, "name": _text(row.name), "quantity": _quantity(row.quantity),
            "unit": _text(row.unit, 50), "checked": row.checked, "source": row.source,
            "category": row.category, "checked_at": _iso(row.checked_at),
            "created_at": _iso(row.created_at)}


def _recipe(meal, *, steps=False):
    raw = meal.recipe_json or {}
    if not isinstance(raw, dict):
        raise HTTPException(422, "Stored recipe is invalid.")
    _bounded(raw)
    ingredients, missing = raw.get("ingredients", []), raw.get("missing_ingredients", [])
    if (not isinstance(ingredients, list) or not isinstance(missing, list)
            or len(ingredients) + len(missing) > MAX_INGREDIENTS):
        raise HTTPException(422, "Recipe has too many ingredients for MCP.")
    result = {"ingredients": [], "missing_ingredients": [_text(value) for value in missing]}
    for item in ingredients:
        if not isinstance(item, dict):
            raise HTTPException(422, "Stored recipe ingredient is invalid.")
        result["ingredients"].append({"name": _text(item.get("name", "")),
                                      "quantity": _quantity(item.get("quantity")),
                                      "unit": _text(item.get("unit") or "unknown", 50)})
    for key in ("servings", "estimated_time_minutes", "cooking_method"):
        if key in raw:
            result[key] = raw[key]
    if steps:
        instructions = raw.get("steps", [])
        if not isinstance(instructions, list) or len(instructions) > 100:
            raise HTTPException(422, "Recipe has too many instructions for MCP.")
        result["steps"] = [_text(step, 4000) for step in instructions]
    return result


def inventory(db: Session, user_id: str, *, query="", limit=50, offset=0) -> dict:
    term = _paging(query, limit, offset, 100)
    rows = db.query(models.InventoryItem).filter_by(user_id=user_id)
    if term:
        rows = rows.filter(func.lower(models.InventoryItem.name).contains(term, autoescape=True))
    found = rows.order_by(models.InventoryItem.id).offset(offset).limit(limit + 1).all()
    return _bounded({"items": [_inventory_item(row) for row in found[:limit]],
                     "limit": limit, "offset": offset, "has_more": len(found) > limit})


def search_recipes(db: Session, user_id: str, *, query="", favorites_only=False,
                   limit=20, offset=0) -> dict:
    term = _paging(query, limit, offset, 50)
    if not isinstance(favorites_only, bool):
        raise HTTPException(422, "favorites_only must be a boolean.")
    rows = db.query(models.Meal).filter(models.Meal.user_id == user_id,
                                       or_(models.Meal.status == "saved", models.Meal.favorite.is_(True)))
    if favorites_only:
        rows = rows.filter(models.Meal.favorite.is_(True))
    if term:
        rows = rows.filter(or_(func.lower(models.Meal.title).contains(term, autoescape=True),
                               func.lower(models.Meal.cuisine).contains(term, autoescape=True)))
    found = rows.order_by(models.Meal.id.desc()).offset(offset).limit(limit + 1).all()
    stock, staples = _stock(db, user_id), _staples(db, user_id)
    result = [{"id": row.id, "title": _text(row.title), "cuisine": row.cuisine,
               "status": row.status, "favorite": row.favorite,
               "recipe": annotate_recipe(_recipe(row, steps=True), stock, staples)}
              for row in found[:limit]]
    return _bounded({"recipes": result, "limit": limit, "offset": offset,
                     "has_more": len(found) > limit,
                     "stock_note": "Stock is evaluated per recipe, not reserved across these recipes."})


def _plan(db, user_id, plan_id=None):
    query = db.query(models.MealPlan).filter_by(user_id=user_id)
    if plan_id is not None:
        if isinstance(plan_id, bool) or not isinstance(plan_id, int) or plan_id < 1:
            raise HTTPException(422, "plan_id must be a positive integer.")
        query = query.filter_by(id=plan_id)
    plan = query.order_by(models.MealPlan.created_at.desc(), models.MealPlan.id.desc()).first()
    if plan is None:
        raise HTTPException(404, "Plan not found.")
    entries = _all_bounded(db.query(models.MealPlanEntry).filter_by(plan_id=plan.id)
                           .order_by(models.MealPlanEntry.slot_index, models.MealPlanEntry.id),
                           MAX_PLAN_ENTRIES)
    # Scope joined children as well, rather than trusting inconsistent legacy FKs.
    meals = {meal.id: meal for meal in db.query(models.Meal)
             .filter(models.Meal.user_id == user_id,
                     models.Meal.id.in_([entry.meal_id for entry in entries])).all()}
    if any(entry.meal_id not in meals for entry in entries):
        raise HTTPException(404, "Plan recipe not found.")
    return plan, [(entry, meals[entry.meal_id]) for entry in entries]


def current_plan(db: Session, user_id: str) -> dict:
    plan, entries = _plan(db, user_id)
    stock, staples = _stock(db, user_id), _staples(db, user_id)
    return _bounded({"id": plan.id, "created_at": _iso(plan.created_at), "status": plan.status,
                     "servings": plan.servings, "start_date": _iso(plan.start_date),
                     "entries": [{"slot_index": entry.slot_index, "meal": {
                         "id": meal.id, "title": _text(meal.title), "status": meal.status,
                         "recipe": annotate_recipe(_recipe(meal), stock, staples)}}
                         for entry, meal in entries],
                     "stock_note": "Stock is evaluated per recipe. Preview shopping to allocate stock across the remaining plan."})


def _original_key(plan_id):
    # Shared with the existing UI import, so the two surfaces cannot double-add.
    return f"shopping:plan:{plan_id}:original"


def _verified_client(client_id):
    if not isinstance(client_id, str) or not client_id or len(client_id) > 255:
        raise HTTPException(403, "Verified OAuth client required.")


def _state(db, user_id, plan_id):
    plan, entries = _plan(db, user_id, plan_id)
    if plan.status != "ready":
        raise HTTPException(409, "Only a ready plan can be previewed or imported through MCP.")
    stock, staples = _stock(db, user_id), _staples(db, user_id)
    shopping = _all_bounded(db.query(models.ShoppingListItem).filter_by(user_id=user_id)
                           .order_by(models.ShoppingListItem.id))
    shopping_data = [_shopping_item(row) for row in shopping]
    receipt = db.query(models.ActionReceipt).filter_by(user_id=user_id,
                                                       action_key=_original_key(plan.id)).one_or_none()
    recipes = [_recipe(meal) for _, meal in entries]
    shopping_list = build_shopping_list(
        [SimpleNamespace(recipe_json=recipe) for (_, meal), recipe in zip(entries, recipes)
         if meal.status == "suggested"], stock, staples)
    # Pure copies prevent the preview's merge from modifying ORM rows.
    copies = [SimpleNamespace(**row) for row in shopping_data]
    updated, creates = merge_into_list(copies, [] if receipt else shopping_list["to_buy"])
    previous = {row.id: row.quantity for row in shopping}
    changes = [{"operation": "update", "item_id": row.id, "name": row.name, "unit": row.unit,
                "previous_quantity": previous[row.id], "quantity": row.quantity,
                "added_quantity": row.quantity - (previous[row.id] or 0)} for row in updated]
    changes += [{"operation": "create", "name": row["name"].strip().lower(),
                 "unit": normalize_unit(row["unit"]), "previous_quantity": None,
                 "quantity": row["quantity"], "added_quantity": row["quantity"]} for row in creates]
    snapshot = _bounded({"plan_id": plan.id, "plan_created_at": _iso(plan.created_at),
                         "meals": [{"id": meal.id, "title": _text(meal.title), "status": meal.status,
                                    "slot_index": entry.slot_index} for entry, meal in entries],
                         **shopping_list, "changes": changes, "already_imported": receipt is not None})
    source = {"plan": {"id": plan.id, "status": plan.status, "updated_at": _iso(plan.updated_at),
                       "servings": plan.servings, "start_date": _iso(plan.start_date)},
              "meals": [{"entry_id": entry.id, "slot_index": entry.slot_index,
                         "id": meal.id, "status": meal.status, "title": meal.title,
                         "recipe": meal.recipe_json} for entry, meal in entries],
              "inventory": [{**_inventory_item(row), "updated_at": _iso(row.updated_at)} for row in stock],
              "staples": staples}
    _bounded(source)
    _bounded(shopping_data)
    return snapshot, _digest(source), _digest({"items": shopping_data, "original_receipt": receipt is not None}), shopping


@contextmanager
def _mutation(db):
    # Public service calls own their transaction. Discard only prior read state;
    # never silently commit/rollback writes supplied by another caller.
    if db.new or db.dirty or db.deleted:
        raise RuntimeError("MCP service requires a clean session.")
    if db.in_transaction():
        db.rollback()
    try:
        if db.get_bind().dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        elif db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            db.execute(text("SET LOCAL statement_timeout = '10s'"))
            db.execute(text("LOCK TABLE action_receipts, inventory_items, meal_plan_entries, "
                            "meal_plans, meals, mcp_shopping_approvals, preferences, shopping_list_items "
                            "IN SHARE ROW EXCLUSIVE MODE"))
        else:
            raise HTTPException(503, "MCP shopping approvals require SQLite or PostgreSQL.")
        yield
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(409, "Kitchen is being updated. Retry after the other change finishes.")
    except Exception:
        db.rollback()
        raise


def _approval(db, user_id, approval_id, client_id=None):
    try:
        canonical_id = str(UUID(approval_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(404, "Approval not found.")
    query = db.query(models.MCPShoppingApproval).filter_by(id=canonical_id, user_id=user_id)
    if client_id is not None:
        query = query.filter_by(client_id=client_id)
    row = query.one_or_none()
    if row is None:
        raise HTTPException(404, "Approval not found.")
    return row


def _approval_out(row):
    status = row.status
    if status in ("pending", "approved") and row.expires_at <= utcnow():
        status = "expired"
    return _bounded({**row.snapshot_json, "approval_id": row.id, "client_id": row.client_id,
                     "status": status, "expires_at": _iso(row.expires_at),
                     "approved_at": _iso(row.approved_at), "result": row.result_json})


def _check_live(row):
    if row.expires_at <= utcnow():
        raise HTTPException(410, "This shopping approval expired. Create a new preview.")
    if row.status not in ("pending", "approved"):
        raise HTTPException(409, "This shopping approval is no longer available. Create a new preview.")


def _check_fresh(db, row):
    try:
        state = _state(db, row.user_id, row.plan_id)
        fresh = state[1] == row.source_digest and state[2] == row.shopping_digest
    except HTTPException as exc:
        if exc.status_code not in (404, 409, 422):
            raise
        fresh = False
    if not fresh:
        row.status = "stale"
        # Preserve the terminal invalidation even though the requested action is
        # rejected. No kitchen mutation has occurred in this transaction.
        db.commit()
        raise HTTPException(409, "The plan, stock, pantry staples, or shopping list changed. Create a new preview.")
    return state


def preview_plan_shopping(db: Session, user_id: str, client_id: str, *,
                          approval_base_url: str, plan_id=None, ttl_seconds=900) -> dict:
    _verified_client(client_id)
    if not isinstance(ttl_seconds, int) or not 60 <= ttl_seconds <= 3600:
        raise HTTPException(503, "Invalid approval lifetime configuration.")
    with _mutation(db):
        snapshot, source_digest, shopping_digest, _ = _state(db, user_id, plan_id)
        active = db.query(models.MCPShoppingApproval).filter(
            models.MCPShoppingApproval.user_id == user_id,
            models.MCPShoppingApproval.status.in_(["pending", "approved"]),
            models.MCPShoppingApproval.expires_at > utcnow())
        row = active.filter_by(client_id=client_id, source_digest=source_digest,
                               shopping_digest=shopping_digest).order_by(models.MCPShoppingApproval.created_at.desc()).first()
        if row is None:
            if active.count() >= 20:
                raise HTTPException(429, "Too many pending shopping approvals. Review them or wait for expiry.")
            row = models.MCPShoppingApproval(id=str(uuid4()), user_id=user_id, client_id=client_id,
                                            plan_id=snapshot["plan_id"], status="pending", snapshot_json=snapshot,
                                            source_digest=source_digest, shopping_digest=shopping_digest,
                                            expires_at=utcnow() + timedelta(seconds=ttl_seconds))
            db.add(row)
            db.flush()
        result = _approval_out(row)
        result["approval_url"] = f"{approval_base_url.rstrip('/')}/mcp-approvals/{row.id}"
        _bounded(result)
    return result


def get_shopping_approval(db: Session, user_id: str, approval_id: str) -> dict:
    return _approval_out(_approval(db, user_id, approval_id))


def approve_shopping(db: Session, user_id: str, approval_id: str) -> dict:
    """First-party human UI only. Never register this function as an MCP tool."""
    with _mutation(db):
        row = _approval(db, user_id, approval_id)
        if row.status != "consumed":
            _check_live(row)
            _check_fresh(db, row)
            if row.status == "pending":
                row.status, row.approved_at = "approved", utcnow()
        result = _approval_out(row)
    return result


def deny_shopping(db: Session, user_id: str, approval_id: str) -> dict:
    with _mutation(db):
        row = _approval(db, user_id, approval_id)
        if row.status == "consumed":
            raise HTTPException(409, "This shopping import has already been applied.")
        if row.status in ("pending", "approved"):
            row.status = "rejected"
        result = _approval_out(row)
    return result


def import_approved_plan_shopping(db: Session, user_id: str, client_id: str, *, approval_id: str) -> dict:
    _verified_client(client_id)
    with _mutation(db):
        row = _approval(db, user_id, approval_id, client_id=client_id)
        if row.status == "consumed":
            return row.result_json  # Stable replay, even after expiry or later edits.
        _check_live(row)
        if row.status != "approved" or row.approved_at is None:
            raise HTTPException(409, "Open the approval URL and explicitly approve in Fridge Chef first.")
        snapshot, _, _, shopping = _check_fresh(db, row)
        if snapshot["already_imported"]:
            result = {"approval_id": row.id, "plan_id": row.plan_id, "status": "already_imported", "items": []}
        else:
            # Locks prevent racing the existing UI's use of the same unique key.
            # Match the UI's empty-import behavior: a no-op must not consume the
            # plan's original key before it ever needs groceries.
            receipt = None
            if row.snapshot_json["to_buy"]:
                receipt = models.ActionReceipt(user_id=user_id, action_key=_original_key(row.plan_id))
                db.add(receipt)
                db.flush()
            updated, creates = merge_into_list(shopping, row.snapshot_json["to_buy"])
            created = [models.ShoppingListItem(user_id=user_id, name=item["name"].strip().lower(),
                                               quantity=item["quantity"], unit=normalize_unit(item["unit"]),
                                               source="plan", category=guess_category(item["name"]))
                       for item in creates]
            db.add_all(created)
            db.flush()
            result = _bounded({"approval_id": row.id, "plan_id": row.plan_id, "status": "imported",
                               "items": [_shopping_item(item) for item in updated + created]})
            if receipt is not None:
                receipt.result_json = result
        row.status, row.consumed_at, row.result_json = "consumed", utcnow(), result
        _approval_out(row)  # The completed approval must remain readable, too.
    return result
