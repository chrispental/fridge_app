"""Standalone shopping list: CRUD, check-off, convert-to-inventory, and imports
from a plan's to-buy list or a meal's missing ingredients."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..models import utcnow
from ..services.shopping_list import build_shopping_list, merge_into_list, missing_for_meal
from ..services.units import normalize_unit

router = APIRouter(prefix="/api/shopping-list", tags=["shopping"])


def _list_items(db: Session) -> list[models.ShoppingListItem]:
    """Unchecked first, newest first within each group."""
    return (
        db.query(models.ShoppingListItem)
        .order_by(
            models.ShoppingListItem.checked,
            models.ShoppingListItem.created_at.desc(),
        )
        .all()
    )


def _staples(db: Session) -> list[str]:
    prefs = db.get(models.Preferences, 1)
    return (prefs.pantry_staples if prefs else None) or []


def _merge_and_save(db: Session, new_items: list[dict], source: str) -> list[models.ShoppingListItem]:
    """Merge imported items into the open list; returns rows added or updated."""
    existing = db.query(models.ShoppingListItem).all()
    updated, creates = merge_into_list(existing, new_items)
    created = [
        models.ShoppingListItem(
            name=str(c["name"]).strip().lower(),
            quantity=c["quantity"],
            unit=normalize_unit(c["unit"]),
            source=source,
        )
        for c in creates
    ]
    db.add_all(created)
    db.commit()
    touched = updated + created
    for row in touched:
        db.refresh(row)
    return touched


# ---- Static routes first (convention; /{item_id} uses other methods anyway) ----

@router.get("", response_model=list[schemas.ShoppingItemOut])
def list_shopping(db: Session = Depends(get_db)):
    return _list_items(db)


@router.post("", response_model=schemas.ShoppingItemOut, status_code=201)
def add_shopping_item(payload: schemas.ShoppingItemCreate, db: Session = Depends(get_db)):
    if not payload.name.strip():
        raise HTTPException(422, "Item name is required.")
    item = models.ShoppingListItem(
        name=payload.name.strip().lower(),
        quantity=payload.quantity,
        unit=normalize_unit(payload.unit),
        source="manual",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/clear-checked", response_model=list[schemas.ShoppingItemOut])
def clear_checked(db: Session = Depends(get_db)):
    """Delete all checked items; returns the remaining list."""
    db.query(models.ShoppingListItem).filter(
        models.ShoppingListItem.checked.is_(True)
    ).delete(synchronize_session=False)
    db.commit()
    return _list_items(db)


@router.post("/checked-to-inventory", response_model=list[schemas.InventoryItemOut])
def checked_to_inventory(db: Session = Depends(get_db)):
    """Convert every checked item into an inventory item (storage 'unsorted'),
    then remove them from the list. The one-tap 'I got everything' flow."""
    checked = (
        db.query(models.ShoppingListItem)
        .filter(models.ShoppingListItem.checked.is_(True))
        .all()
    )
    created: list[models.InventoryItem] = []
    for row in checked:
        created.append(
            models.InventoryItem(
                name=row.name.strip().lower(),
                quantity=row.quantity,
                unit=normalize_unit(row.unit),
                storage="unsorted",
                source="manual",
            )
        )
        db.add(created[-1])
        db.delete(row)
    db.commit()
    for item in created:
        db.refresh(item)
    return created


@router.post("/import/plan/{plan_id}", response_model=list[schemas.ShoppingItemOut])
def import_plan(plan_id: int, db: Session = Depends(get_db)):
    """Merge a plan's to-buy list into the shopping list."""
    plan = db.get(models.MealPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    inventory = db.query(models.InventoryItem).all()
    meals = [e.meal for e in plan.entries]
    to_buy = build_shopping_list(meals, inventory, _staples(db))["to_buy"]
    return _merge_and_save(db, to_buy, source="plan")


@router.post("/import/meal/{meal_id}", response_model=list[schemas.ShoppingItemOut])
def import_meal(meal_id: int, db: Session = Depends(get_db)):
    """Merge one meal's missing ingredients into the shopping list."""
    meal = db.get(models.Meal, meal_id)
    if meal is None:
        raise HTTPException(404, "Meal not found")
    inventory = db.query(models.InventoryItem).all()
    needed = missing_for_meal(meal.recipe_json or {}, inventory, _staples(db))
    return _merge_and_save(db, needed, source="meal")


# ---- Dynamic routes ----

@router.patch("/{item_id}", response_model=schemas.ShoppingItemOut)
def update_shopping_item(
    item_id: int,
    payload: schemas.ShoppingItemUpdate,
    db: Session = Depends(get_db),
):
    item = db.get(models.ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("name"):
        item.name = data["name"].strip().lower()
    if "quantity" in data:
        item.quantity = data["quantity"]
    if data.get("unit"):
        item.unit = normalize_unit(data["unit"])
    if "checked" in data and data["checked"] is not None:
        item.checked = data["checked"]
        item.checked_at = utcnow() if data["checked"] else None
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_shopping_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()
