"""Data portability: everything the user owns as one JSON document.

Plain, versioned, and readable without the app: preferences, inventory, the full
meal log (including the recipe book and feedback), the shopping list, and plans.
Photos are not included (they live in blob storage), only the scan metadata.
"""
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import CurrentUser
from ..database import get_db
from ..models import utcnow
from ..services.scope import get_prefs

router = APIRouter(prefix="/api/export", tags=["export"])

EXPORT_FORMAT = "fridge-chef-export/1"


def build_export(db: Session, user_id: str) -> dict:
    prefs = get_prefs(db, user_id)
    inventory = db.query(models.InventoryItem).filter_by(user_id=user_id).order_by(models.InventoryItem.id).all()
    meals = db.query(models.Meal).filter_by(user_id=user_id).order_by(models.Meal.id).all()
    shopping = db.query(models.ShoppingListItem).filter_by(user_id=user_id).order_by(models.ShoppingListItem.id).all()
    plans = db.query(models.MealPlan).filter_by(user_id=user_id).order_by(models.MealPlan.id).all()
    scans = db.query(models.ExtractionBatch).filter_by(user_id=user_id).order_by(models.ExtractionBatch.id).all()
    return {
        "format": EXPORT_FORMAT,
        "exported_at": utcnow(),
        "preferences": schemas.PreferencesOut.model_validate(prefs).model_dump(exclude={"id"}),
        "inventory": [schemas.InventoryItemOut.model_validate(i).model_dump(exclude={"image_url"}) for i in inventory],
        "meals": [schemas.MealOut.model_validate(m).model_dump(exclude={"not_subtracted"}) for m in meals],
        "shopping_list": [schemas.ShoppingItemOut.model_validate(s).model_dump() for s in shopping],
        "plans": [
            {
                "id": p.id, "created_at": p.created_at, "status": p.status,
                "requested_count": p.requested_count, "servings": p.servings, "start_date": p.start_date,
                "meal_ids": [e.meal_id for e in p.entries],
            }
            for p in plans
        ],
        "scans": [{"id": b.id, "created_at": b.created_at, "status": b.status} for b in scans],
    }


@router.get("")
def export_data(user: CurrentUser, db: Session = Depends(get_db)):
    """Download the user's kitchen as a JSON file."""
    payload = jsonable_encoder(build_export(db, user.id))
    stamp = payload["exported_at"][:10]
    return JSONResponse(
        payload,
        headers={"Content-Disposition": f'attachment; filename="fridge-chef-export-{stamp}.json"'},
    )
