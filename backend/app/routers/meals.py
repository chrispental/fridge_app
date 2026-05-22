"""Meal suggestion, history, cook logging, and weekly delivery."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..models import utcnow
from ..services import brave_search
from ..services.meal_engine import most_recent_delivery, suggest_meals
from ..services.units import try_subtract

router = APIRouter(prefix="/api/meals", tags=["meals"])


def _delivery_status(db: Session) -> schemas.DeliveryStatusOut:
    """Whether this week's single delivery slot is still available."""
    last = most_recent_delivery(db)
    if last is None or last.delivery_ordered_at is None:
        return schemas.DeliveryStatusOut(used=False, remaining=1, next_available_at=None)
    return schemas.DeliveryStatusOut(
        used=True,
        remaining=0,
        next_available_at=last.delivery_ordered_at + timedelta(days=7),
    )


@router.post("/suggest", response_model=list[schemas.MealOut])
def suggest(
    count: int = Query(default=3, ge=1, le=3),
    db: Session = Depends(get_db),
):
    try:
        meals = suggest_meals(db, count=count)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    if not meals:
        raise HTTPException(
            422,
            "Couldn't find a meal that fits. Try adding more to your inventory "
            "or relaxing your preferences.",
        )
    return meals


@router.get("", response_model=list[schemas.MealOut])
def list_meals(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models.Meal)
    if status:
        query = query.filter(models.Meal.status == status)
    return (
        query.order_by(models.Meal.suggested_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# Declared before the dynamic /{meal_id} route so "delivery" isn't read as an id.
@router.get("/delivery/status", response_model=schemas.DeliveryStatusOut)
def delivery_status(db: Session = Depends(get_db)):
    return _delivery_status(db)


@router.get("/{meal_id}", response_model=schemas.MealOut)
def get_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.get(models.Meal, meal_id)
    if meal is None:
        raise HTTPException(404, "Meal not found")
    return meal


@router.post("/{meal_id}/order-delivery", response_model=schemas.MealOut)
def order_delivery(meal_id: int, db: Session = Depends(get_db)):
    """Mark a meal as ordered for delivery (one per rolling 7 days) and attach order links."""
    meal = db.get(models.Meal, meal_id)
    if meal is None:
        raise HTTPException(404, "Meal not found")

    prefs = db.get(models.Preferences, 1)
    if not prefs or not prefs.location:
        raise HTTPException(422, "Set your location in Settings to order delivery.")

    status = _delivery_status(db)
    if status.used:
        when = status.next_available_at.date().isoformat() if status.next_available_at else "soon"
        raise HTTPException(
            409, f"Weekly delivery already used. Next available {when}."
        )

    meal.delivery_ordered_at = utcnow()
    meal.status = "ordered"

    # Best-effort: find places to order this dish nearby. Never blocks the order.
    links = brave_search.search_web(
        f"{meal.title} delivery near {prefs.location}", count=5
    )
    meal.recipe_json = {**(meal.recipe_json or {}), "delivery_options": links}

    db.commit()
    db.refresh(meal)
    return meal


@router.post("/{meal_id}/cook", response_model=schemas.MealOut)
def cook_meal(
    meal_id: int,
    payload: schemas.CookRequest,
    db: Session = Depends(get_db),
):
    meal = db.get(models.Meal, meal_id)
    if meal is None:
        raise HTTPException(404, "Meal not found")
    meal.status = "cooked"
    meal.cooked_at = utcnow()
    if payload.decrement_inventory:
        _decrement_inventory(db, meal)
    db.commit()
    db.refresh(meal)
    return meal


@router.delete("/{meal_id}", status_code=204)
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.get(models.Meal, meal_id)
    if meal is None:
        raise HTTPException(404, "Meal not found")
    db.delete(meal)
    db.commit()


def _decrement_inventory(db: Session, meal: models.Meal) -> None:
    """Best-effort: subtract a cooked meal's in-stock ingredients from inventory."""
    ingredients = (meal.recipe_json or {}).get("ingredients", [])
    inventory = db.query(models.InventoryItem).all()
    for ing in ingredients:
        if not ing.get("in_stock"):
            continue
        name = (ing.get("name") or "").lower().strip()
        if not name:
            continue
        match = next(
            (i for i in inventory if name in i.name or i.name in name), None
        )
        if match is None or match.quantity is None or ing.get("quantity") is None:
            continue
        new_qty = try_subtract(
            match.quantity, match.unit, ing["quantity"], ing.get("unit", "unknown")
        )
        if new_qty is None:
            continue
        if new_qty <= 0:
            db.delete(match)
        else:
            match.quantity = new_qty
