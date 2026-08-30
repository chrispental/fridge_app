"""Weekly meal plan: create a plan, view the current one, swap a day, and derive a
live shopping list (have vs. to-buy) for it."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import CurrentUser
from ..database import get_db
from ..services.meal_engine import create_plan, swap_slot
from ..services.scope import get_owned, inventory_for, staples_for
from ..services.shopping_list import annotate_recipe, build_shopping_list

router = APIRouter(prefix="/api/plans", tags=["plans"])


def _owned_plan(db: Session, plan_id: int, user_id: str) -> models.MealPlan:
    return get_owned(db, models.MealPlan, plan_id, user_id, label="Plan")


def _serialize_plan(db: Session, user_id: str, plan: models.MealPlan) -> schemas.MealPlanOut:
    """Build the plan response, recomputing each meal's in-stock / missing-ingredient
    state live (against current inventory + staples) so cards match the shopping list."""
    inventory = inventory_for(db, user_id)
    staples = staples_for(db, user_id)
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
            rating=m.rating,
            feedback_tags=m.feedback_tags,
            feedback_notes=m.feedback_notes,
            feedback_at=m.feedback_at,
        )
        entries.append(schemas.MealPlanEntryOut(slot_index=e.slot_index, meal=meal_out))
    return schemas.MealPlanOut(id=plan.id, created_at=plan.created_at, entries=entries)


@router.post("", response_model=schemas.MealPlanOut)
def create(payload: schemas.CreatePlanRequest, user: CurrentUser, db: Session = Depends(get_db)):
    try:
        plan = create_plan(db, user.id, count=payload.count)
    except RuntimeError as exc:  # AI/provider failure (mirrors /meals/suggest)
        raise HTTPException(502, str(exc))
    if not plan.entries:
        raise HTTPException(
            422,
            "Couldn't plan any meals. Try adding more to your inventory or "
            "relaxing your preferences.",
        )
    return _serialize_plan(db, user.id, plan)


# Declared before the dynamic /{plan_id} route so "current" isn't read as an id.
@router.get("/current", response_model=schemas.MealPlanOut)
def current(user: CurrentUser, db: Session = Depends(get_db)):
    plan = (
        db.query(models.MealPlan)
        .filter(models.MealPlan.user_id == user.id)
        .order_by(models.MealPlan.created_at.desc())
        .first()
    )
    if plan is None:
        raise HTTPException(404, "No plan yet")
    return _serialize_plan(db, user.id, plan)


@router.get("/{plan_id}/shopping-list", response_model=schemas.ShoppingListOut)
def shopping_list(plan_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    plan = _owned_plan(db, plan_id, user.id)
    meals = [e.meal for e in plan.entries]
    return build_shopping_list(meals, inventory_for(db, user.id), staples_for(db, user.id))


@router.post(
    "/{plan_id}/slots/{slot_index}/swap", response_model=schemas.MealPlanOut
)
def swap(plan_id: int, slot_index: int, user: CurrentUser, db: Session = Depends(get_db)):
    plan = _owned_plan(db, plan_id, user.id)
    entry = next((e for e in plan.entries if e.slot_index == slot_index), None)
    if entry is None:
        raise HTTPException(404, "Plan slot not found")
    try:
        new_meal = swap_slot(db, user.id, entry)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    if new_meal is None:
        raise HTTPException(422, "Couldn't find a replacement meal. Try again.")
    db.refresh(plan)
    return _serialize_plan(db, user.id, plan)


@router.delete("/{plan_id}", status_code=204)
def delete(plan_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    plan = _owned_plan(db, plan_id, user.id)
    db.delete(plan)  # cascade removes entries; Meal history is left intact
    db.commit()
