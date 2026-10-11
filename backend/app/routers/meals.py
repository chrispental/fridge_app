"""Meal suggestion, history, cook logging, and weekly delivery."""
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import CurrentUser
from ..database import get_db
from ..models import utcnow
from ..services import brave_search
from ..services.expiry import estimate_expiry
from ..services.recipe_import import ImportError_, import_recipe
from ..services.meal_engine import AdjustmentRejected, adjust_meal, most_recent_delivery, normalize_title, suggest_meals
from ..services.meal_stats import compute_stats
from ..services.scope import get_owned, get_prefs, inventory_for, staples_for
from ..services.ingredients import StockPool
from ..services.shopping_list import annotate_recipe
from ..services.actions import claim_action

router = APIRouter(prefix="/api/meals", tags=["meals"])


def _owned_meal(db: Session, meal_id: int, user_id: str) -> models.Meal:
    return get_owned(db, models.Meal, meal_id, user_id, label="Meal")


def _annotated(db: Session, user_id: str, meal: models.Meal) -> schemas.MealOut:
    return schemas.MealOut.model_validate(meal).model_copy(update={
        "recipe_json": annotate_recipe(meal.recipe_json, inventory_for(db, user_id), staples_for(db, user_id))
    })


def _recipe_copy(meal: models.Meal, *, status: str) -> models.Meal:
    """A fresh Meal row carrying a saved recipe's content, so cooking or planning a
    recipe from the book is logged like any other meal while the book entry stays put."""
    recipe = {k: v for k, v in (meal.recipe_json or {}).items() if k != "delivery_options"}
    return models.Meal(
        user_id=meal.user_id,
        title=meal.title,
        title_normalized=meal.title_normalized,
        cuisine=meal.cuisine,
        recipe_json={**recipe, "saved_from": meal.id},
        status=status,
        suggested_at=utcnow(),
    )


# A dish-name search mostly returns recipe pages; only links on a delivery service
# are useful as "order links".
DELIVERY_HOSTS = (
    "doordash.com", "ubereats.com", "grubhub.com", "postmates.com", "seamless.com",
    "delivery.com", "caviar.com", "chownow.com", "slicelife.com", "ezcater.com",
)


def _delivery_links(title: str, location: str) -> list[dict]:
    """Brave results for ordering this dish nearby, limited to delivery services."""
    # `location` sets Brave's X-Loc-* headers so results actually serve the user's area.
    results = brave_search.search_web(f"{title} restaurant delivery", count=15, location=location)
    links = []
    for result in results:
        host = (urlsplit(result.get("url") or "").hostname or "").lower()
        if any(host == known or host.endswith("." + known) for known in DELIVERY_HOSTS):
            links.append(result)
    return links[:5]


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
        meals = suggest_meals(db, user.id, count=payload.count, idea=payload.idea, servings=payload.servings)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    if not meals:
        raise HTTPException(
            422,
            "Couldn't find a meal that fits. Try adding more to your inventory "
            "or relaxing your preferences.",
        )
    return meals


@router.post("/import", response_model=schemas.MealOut, status_code=201)
def import_saved_recipe(
    payload: schemas.ImportRecipeRequest, user: CurrentUser, db: Session = Depends(get_db)
):
    """Save a recipe from a web address or pasted text into the user's recipe book."""
    try:
        recipe = import_recipe(url=payload.url, text=payload.text)
    except ImportError_ as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    meal = models.Meal(
        user_id=user.id,
        title=recipe.title,
        title_normalized=normalize_title(recipe.title),
        cuisine=recipe.cuisine,
        recipe_json=recipe.model_dump(),
        status="saved",
        suggested_at=utcnow(),
    )
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return _annotated(db, user.id, meal)


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
    else:
        # The recipe book is its own list (see /recipes); history is what was served.
        query = query.filter(models.Meal.status != "saved")
    if q and q.strip():
        # Both sides are lowercased by normalize_title, so LIKE is effectively
        # case-insensitive on Postgres too.
        query = query.filter(
            models.Meal.title_normalized.contains(normalize_title(q))
        )
    rows = (
        query.order_by(models.Meal.suggested_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    inventory = inventory_for(db, user.id)
    staples = get_prefs(db, user.id).pantry_staples or []
    return [schemas.MealOut.model_validate(m).model_copy(update={
        "recipe_json": annotate_recipe(m.recipe_json, inventory, staples)
    }) for m in rows]


# Declared before the dynamic /{meal_id} route so "delivery" isn't read as an id.
@router.get("/delivery/status", response_model=schemas.DeliveryStatusOut)
def delivery_status(user: CurrentUser, db: Session = Depends(get_db)):
    return _delivery_status(db, user.id)


# Also declared before /{meal_id} so "stats" isn't read as an id.
@router.get("/stats", response_model=schemas.MealStatsOut)
def meal_stats(user: CurrentUser, db: Session = Depends(get_db)):
    staples = get_prefs(db, user.id).pantry_staples or []
    meals = db.query(models.Meal).filter(models.Meal.user_id == user.id, models.Meal.status != "saved").all()
    return compute_stats(meals, staples=staples, now=utcnow())


# The recipe book: imported recipes plus anything marked favourite, newest first.
@router.get("/recipes", response_model=list[schemas.MealOut])
def list_recipes(user: CurrentUser, q: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Meal).filter(
        models.Meal.user_id == user.id,
        (models.Meal.status == "saved") | (models.Meal.favorite.is_(True)),
    )
    if q and q.strip():
        query = query.filter(models.Meal.title_normalized.contains(normalize_title(q)))
    rows = query.order_by(models.Meal.suggested_at.desc()).limit(200).all()
    inventory = inventory_for(db, user.id)
    staples = staples_for(db, user.id)
    return [schemas.MealOut.model_validate(m).model_copy(update={
        "recipe_json": annotate_recipe(m.recipe_json, inventory, staples)
    }) for m in rows]


@router.get("/{meal_id}", response_model=schemas.MealOut)
def get_meal(meal_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    meal = _owned_meal(db, meal_id, user.id)
    return schemas.MealOut.model_validate(meal).model_copy(update={
        "recipe_json": annotate_recipe(meal.recipe_json, inventory_for(db, user.id), get_prefs(db, user.id).pantry_staples or [])
    })


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
    links = _delivery_links(meal.title, prefs.location)
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
    if payload.request_id:
        receipt, claimed = claim_action(db, user.id, f"cook:{meal_id}:{payload.request_id}")
        if not claimed:
            logged = receipt.result_json and receipt.result_json.get("meal_id")
            return db.get(models.Meal, logged) if logged else meal
    elif meal.status == "cooked":
        # Older clients can safely retry; a deliberate new cook sends a new id.
        return meal
    if meal.status == "saved":
        # The book entry stays; the cook is logged on a fresh row (returned to the client).
        source = meal
        meal = _recipe_copy(source, status="cooked")
        db.add(meal)
        db.flush()
        if payload.request_id:
            receipt.result_json = {"meal_id": meal.id}
    meal.status = "cooked"
    meal.cooked_at = utcnow()
    not_subtracted = _decrement_inventory(db, meal) if payload.decrement_inventory else []
    if payload.save_leftovers:
        _save_leftovers(db, meal)
    db.commit()
    db.refresh(meal)
    # Response-only: tells the client which stocked ingredients it must adjust by hand.
    meal.not_subtracted = not_subtracted
    return meal


@router.post("/{meal_id}/adjust", response_model=schemas.MealOut)
def adjust(
    meal_id: int,
    payload: schemas.AdjustRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Rewrite a suggested recipe from a short instruction ("make it vegetarian")."""
    meal = _owned_meal(db, meal_id, user.id)
    if meal.status not in ("suggested", "saved"):
        raise HTTPException(409, "This meal is already cooked or ordered. Ask for a new suggestion instead.")
    try:
        adjust_meal(db, user.id, meal, payload.instruction)
    except AdjustmentRejected as exc:
        raise HTTPException(422, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))
    return _annotated(db, user.id, meal)


@router.post("/{meal_id}/favorite", response_model=schemas.MealOut)
def set_favorite(
    meal_id: int,
    payload: schemas.FavoriteRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Pin (or unpin) a meal in the recipe book; favourites are hinted to the planner."""
    meal = _owned_meal(db, meal_id, user.id)
    meal.favorite = payload.favorite
    db.commit()
    db.refresh(meal)
    return _annotated(db, user.id, meal)


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
    if db.query(models.MealPlanEntry).filter_by(meal_id=meal.id).first():
        raise HTTPException(409, "Remove this meal's plan before deleting the recipe.")
    db.delete(meal)
    db.commit()


def _save_leftovers(db: Session, meal: models.Meal) -> models.InventoryItem:
    """Put tonight's leftovers in the fridge as an inventory item with a short expiry,
    so "use these first" and the meal engine see them. The amount is unknown by design."""
    item = models.InventoryItem(
        user_id=meal.user_id,
        name=f"leftover {meal.title}".strip().lower(),
        quantity=None,
        unit="unknown",
        category="leftover",
        storage="fridge",
        expires_at=estimate_expiry("leftover", "fridge"),
        source="leftover",
    )
    db.add(item)
    return item


def _decrement_inventory(db: Session, meal: models.Meal) -> list[str]:
    """Best-effort: subtract a cooked meal's in-stock ingredients from inventory.

    Returns the ingredients that are stocked but could not be subtracted because
    their amount or unit is unknown or incompatible.
    """
    not_subtracted = []
    ingredients = (meal.recipe_json or {}).get("ingredients", [])
    inventory = inventory_for(db, meal.user_id, lock=True)
    pool = StockPool(inventory)
    for ing in ingredients:
        name = (ing.get("name") or "").lower().strip()
        if not name:
            continue
        stock = pool.allocate(name, ing.get("quantity"), ing.get("unit"))
        for match, amount in stock["allocations"]:
            match.quantity = max(0, match.quantity - amount)
        if stock["stock_status"] == "check":
            not_subtracted.append(name)
    for item in inventory:
        if item.quantity == 0:
            db.delete(item)
    return not_subtracted
