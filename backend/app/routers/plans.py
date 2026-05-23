"""Weekly meal plan: create a plan, view the current one, swap a day, and derive a
live shopping list (have vs. to-buy) for it."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.meal_engine import create_plan, swap_slot
from ..services.shopping_list import annotate_recipe, build_shopping_list

router = APIRouter(prefix="/api/plans", tags=["plans"])


def _get_plan_or_404(db: Session, plan_id: int) -> models.MealPlan:
    plan = db.get(models.MealPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    return plan


def _serialize_plan(db: Session, plan: models.MealPlan) -> schemas.MealPlanOut:
    """Build the plan response, recomputing each meal's in-stock / missing-ingredient
    state live (against current inventory + staples) so cards match the shopping list."""
    prefs = db.get(models.Preferences, 1)
    inventory = db.query(models.InventoryItem).all()
    staples = (prefs.pantry_staples if prefs else None) or []
    entries = []
    for e in plan.entries:
        m = e.meal
        meal_out = schemas.MealOut(
            id=m.id,
            title=m.title,
            cuisine=m.cuisine,
            recipe_json=annotate_recipe(m.recipe_json, inventory, staples),
            status=m.status,
            suggested_at=m.suggested_at,
            cooked_at=m.cooked_at,
            delivery_ordered_at=m.delivery_ordered_at,
        )
        entries.append(schemas.MealPlanEntryOut(slot_index=e.slot_index, meal=meal_out))
    return schemas.MealPlanOut(id=plan.id, created_at=plan.created_at, entries=entries)


@router.post("", response_model=schemas.MealPlanOut)
def create(payload: schemas.CreatePlanRequest, db: Session = Depends(get_db)):
    try:
        plan = create_plan(db, count=payload.count)
    except RuntimeError as exc:  # AI/provider failure (mirrors /meals/suggest)
        raise HTTPException(502, str(exc))
    if not plan.entries:
        raise HTTPException(
            422,
            "Couldn't plan any meals. Try adding more to your inventory or "
            "relaxing your preferences.",
        )
    return _serialize_plan(db, plan)


# Declared before the dynamic /{plan_id} route so "current" isn't read as an id.
@router.get("/current", response_model=schemas.MealPlanOut)
def current(db: Session = Depends(get_db)):
    plan = (
        db.query(models.MealPlan).order_by(models.MealPlan.created_at.desc()).first()
    )
    if plan is None:
        raise HTTPException(404, "No plan yet")
    return _serialize_plan(db, plan)


@router.get("/{plan_id}/shopping-list", response_model=schemas.ShoppingListOut)
def shopping_list(plan_id: int, db: Session = Depends(get_db)):
    plan = _get_plan_or_404(db, plan_id)
    prefs = db.get(models.Preferences, 1)
    inventory = db.query(models.InventoryItem).all()
    staples = (prefs.pantry_staples if prefs else None) or []
    meals = [e.meal for e in plan.entries]
    return build_shopping_list(meals, inventory, staples)


@router.post(
    "/{plan_id}/slots/{slot_index}/swap", response_model=schemas.MealPlanOut
)
def swap(plan_id: int, slot_index: int, db: Session = Depends(get_db)):
    plan = _get_plan_or_404(db, plan_id)
    entry = next((e for e in plan.entries if e.slot_index == slot_index), None)
    if entry is None:
        raise HTTPException(404, "Plan slot not found")
    try:
        new_meal = swap_slot(db, entry)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    if new_meal is None:
        raise HTTPException(422, "Couldn't find a replacement meal. Try again.")
    db.refresh(plan)
    return _serialize_plan(db, plan)


@router.delete("/{plan_id}", status_code=204)
def delete(plan_id: int, db: Session = Depends(get_db)):
    plan = _get_plan_or_404(db, plan_id)
    db.delete(plan)  # cascade removes entries; Meal history is left intact
    db.commit()
