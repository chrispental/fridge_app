"""Standalone shopping list: CRUD, check-off, convert-to-inventory, and imports
from a plan's to-buy list or a meal's missing ingredients."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import CurrentUser
from ..database import get_db
from ..models import utcnow
from ..services.scope import get_owned, inventory_for, staples_for
from ..services.shopping_list import build_shopping_list, merge_into_list, missing_for_meal
from ..services.units import normalize_unit

router = APIRouter(prefix="/api/shopping-list", tags=["shopping"])


def _owned_row(db: Session, item_id: int, user_id: str) -> models.ShoppingListItem:
    return get_owned(db, models.ShoppingListItem, item_id, user_id, label="Item")


def _list_items(db: Session, user_id: str) -> list[models.ShoppingListItem]:
    """Unchecked first, newest first within each group."""
    return (
        db.query(models.ShoppingListItem)
        .filter(models.ShoppingListItem.user_id == user_id)
        .order_by(
            models.ShoppingListItem.checked,
            models.ShoppingListItem.created_at.desc(),
        )
        .all()
    )


def _merge_and_save(
    db: Session, user_id: str, new_items: list[dict], source: str
) -> list[models.ShoppingListItem]:
    """Merge imported items into the open list; returns rows added or updated."""
    existing = (
        db.query(models.ShoppingListItem)
        .filter(models.ShoppingListItem.user_id == user_id)
        .all()
    )
    updated, creates = merge_into_list(existing, new_items)
    created = [
        models.ShoppingListItem(
            user_id=user_id,
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
def list_shopping(user: CurrentUser, db: Session = Depends(get_db)):
    return _list_items(db, user.id)


@router.post("", response_model=schemas.ShoppingItemOut, status_code=201)
def add_shopping_item(
    payload: schemas.ShoppingItemCreate, user: CurrentUser, db: Session = Depends(get_db)
):
    if not payload.name.strip():
        raise HTTPException(422, "Item name is required.")
    item = models.ShoppingListItem(
        user_id=user.id,
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
def clear_checked(user: CurrentUser, db: Session = Depends(get_db)):
    """Delete all checked items; returns the remaining list."""
    db.query(models.ShoppingListItem).filter(
        models.ShoppingListItem.user_id == user.id,
        models.ShoppingListItem.checked.is_(True),
    ).delete(synchronize_session=False)
    db.commit()
    return _list_items(db, user.id)


@router.post("/checked-to-inventory", response_model=list[schemas.InventoryItemOut])
def checked_to_inventory(user: CurrentUser, db: Session = Depends(get_db)):
    """Convert every checked item into an inventory item (storage 'unsorted'),
    then remove them from the list. The one-tap 'I got everything' flow."""
    checked = (
        db.query(models.ShoppingListItem)
        .filter(
            models.ShoppingListItem.user_id == user.id,
            models.ShoppingListItem.checked.is_(True),
        )
        .all()
    )
    created: list[models.InventoryItem] = []
    for row in checked:
        created.append(
            models.InventoryItem(
                user_id=user.id,
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
def import_plan(plan_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """Merge a plan's to-buy list into the shopping list."""
    plan = get_owned(db, models.MealPlan, plan_id, user.id, label="Plan")
    meals = [e.meal for e in plan.entries]
    to_buy = build_shopping_list(
        meals, inventory_for(db, user.id), staples_for(db, user.id)
    )["to_buy"]
    return _merge_and_save(db, user.id, to_buy, source="plan")


@router.post("/import/meal/{meal_id}", response_model=list[schemas.ShoppingItemOut])
def import_meal(meal_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """Merge one meal's missing ingredients into the shopping list."""
    meal = get_owned(db, models.Meal, meal_id, user.id, label="Meal")
    needed = missing_for_meal(
        meal.recipe_json or {}, inventory_for(db, user.id), staples_for(db, user.id)
    )
    return _merge_and_save(db, user.id, needed, source="meal")


# ---- Dynamic routes ----

@router.patch("/{item_id}", response_model=schemas.ShoppingItemOut)
def update_shopping_item(
    item_id: int,
    payload: schemas.ShoppingItemUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    item = _owned_row(db, item_id, user.id)
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
def delete_shopping_item(item_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    item = _owned_row(db, item_id, user.id)
    db.delete(item)
    db.commit()
