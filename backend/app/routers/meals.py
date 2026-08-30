"""Meal suggestion, history, cook logging, and weekly delivery."""
from datetime import timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import CurrentUser
from ..database import get_db
from ..models import utcnow
from ..services import brave_search
from ..services.meal_engine import most_recent_delivery, normalize_title, suggest_meals
from ..services.meal_stats import compute_stats
from ..services.scope import get_owned, get_prefs, inventory_for
from ..services.units import try_subtract

router = APIRouter(prefix="/api/meals", tags=["meals"])


def _owned_meal(db: Session, meal_id: int, user_id: str) -> models.Meal:
    return get_owned(db, models.Meal, meal_id, user_id, label="Meal")


def _delivery_status(db: Session, user_id: str) -> schemas.DeliveryStatusOut:
    """Whether this week's single delivery slot is still available."""
    last = most_recent_delivery(db, user_id)
    if last is None or last.delivery_ordered_at is None:
        return schemas.DeliveryStatusOut(used=False, remaining=1, next_available_at=None)
    return schemas.DeliveryStatusOut(
        used=True,
        remaining=0,
        next_available_at=last.delivery_ordered_at + timedelta(days=7),
    )


@router.post("/suggest", response_model=list[schemas.MealOut])
def suggest(
    user: CurrentUser,
    payload: schemas.SuggestRequest = Body(default_factory=schemas.SuggestRequest),
    db: Session = Depends(get_db),
):
    try:
        meals = suggest_meals(db, user.id, count=payload.count, idea=payload.idea)
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
    user: CurrentUser,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models.Meal).filter(models.Meal.user_id == user.id)
    if status:
        query = query.filter(models.Meal.status == status)
    if q and q.strip():
        # Both sides are lowercased by normalize_title, so LIKE is effectively
        # case-insensitive on Postgres too.
        query = query.filter(
            models.Meal.title_normalized.contains(normalize_title(q))
        )
    return (
        query.order_by(models.Meal.suggested_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# Declared before the dynamic /{meal_id} route so "delivery" isn't read as an id.
@router.get("/delivery/status", response_model=schemas.DeliveryStatusOut)
def delivery_status(user: CurrentUser, db: Session = Depends(get_db)):
    return _delivery_status(db, user.id)


# Also declared before /{meal_id} so "stats" isn't read as an id.
@router.get("/stats", response_model=schemas.MealStatsOut)
def meal_stats(user: CurrentUser, db: Session = Depends(get_db)):
    staples = get_prefs(db, user.id).pantry_staples or []
    meals = db.query(models.Meal).filter(models.Meal.user_id == user.id).all()
    return compute_stats(meals, staples=staples, now=utcnow())


@router.get("/{meal_id}", response_model=schemas.MealOut)
def get_meal(meal_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    return _owned_meal(db, meal_id, user.id)


@router.post("/{meal_id}/order-delivery", response_model=schemas.MealOut)
def order_delivery(meal_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """Mark a meal as ordered for delivery (one per rolling 7 days) and attach order links."""
    meal = _owned_meal(db, meal_id, user.id)

    prefs = get_prefs(db, user.id)
    if not prefs.location:
        raise HTTPException(422, "Set your location in Settings to order delivery.")

    status = _delivery_status(db, user.id)
    if status.used:
        when = status.next_available_at.date().isoformat() if status.next_available_at else "soon"
        raise HTTPException(
            409, f"Weekly delivery already used. Next available {when}."
        )

    meal.delivery_ordered_at = utcnow()
    meal.status = "ordered"

    # Best-effort: find places to order this dish nearby. Never blocks the order.
    # `location` sets Brave's X-Loc-* headers so results actually serve the user's area.
    links = brave_search.search_web(
        f"{meal.title} restaurant delivery", count=5, location=prefs.location
    )
    meal.recipe_json = {**(meal.recipe_json or {}), "delivery_options": links}

    db.commit()
    db.refresh(meal)
    return meal


@router.post("/{meal_id}/cook", response_model=schemas.MealOut)
def cook_meal(
    meal_id: int,
    payload: schemas.CookRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    meal = _owned_meal(db, meal_id, user.id)
    meal.status = "cooked"
    meal.cooked_at = utcnow()
    if payload.decrement_inventory:
        _decrement_inventory(db, meal)
    db.commit()
    db.refresh(meal)
    return meal


@router.post("/{meal_id}/feedback", response_model=schemas.MealOut)
def submit_feedback(
    meal_id: int,
    payload: schemas.FeedbackRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Record (or update) post-cook feedback used to tailor future suggestions."""
    meal = _owned_meal(db, meal_id, user.id)
    # Normalize rating to 1 / -1 / None so downstream logic is simple.
    meal.rating = 1 if (payload.rating or 0) > 0 else -1 if (payload.rating or 0) < 0 else None
    meal.feedback_tags = [t.strip() for t in payload.tags if t and t.strip()]
    meal.feedback_notes = (payload.notes or "").strip() or None
    meal.feedback_at = utcnow()
    db.commit()
    db.refresh(meal)
    return meal


@router.delete("/{meal_id}", status_code=204)
def delete_meal(meal_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    meal = _owned_meal(db, meal_id, user.id)
    db.delete(meal)
    db.commit()


def _decrement_inventory(db: Session, meal: models.Meal) -> None:
    """Best-effort: subtract a cooked meal's in-stock ingredients from inventory."""
    ingredients = (meal.recipe_json or {}).get("ingredients", [])
    inventory = inventory_for(db, meal.user_id)
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
