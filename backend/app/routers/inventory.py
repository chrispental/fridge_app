"""Inventory CRUD + photo-based extraction (extract -> review -> confirm)."""
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.units import normalize_unit
from ..services.vision import extract_items, parse_items, preprocess_and_save

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

MAX_UPLOAD_BYTES = 12 * 1024 * 1024  # 12 MB


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
@router.get("", response_model=list[schemas.InventoryItemOut])
def list_inventory(category: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.InventoryItem)
    if category:
        query = query.filter(models.InventoryItem.category == category)
    return query.order_by(models.InventoryItem.added_at.desc()).all()


@router.post("", response_model=schemas.InventoryItemOut, status_code=201)
def add_item(payload: schemas.InventoryItemCreate, db: Session = Depends(get_db)):
    item = models.InventoryItem(
        name=payload.name.strip().lower(),
        quantity=payload.quantity,
        unit=normalize_unit(payload.unit),
        category=payload.category,
        source="manual",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=schemas.InventoryItemOut)
def update_item(
    item_id: int,
    payload: schemas.InventoryItemUpdate,
    db: Session = Depends(get_db),
):
    item = db.get(models.InventoryItem, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("name"):
        item.name = data["name"].strip().lower()
    if "quantity" in data:
        item.quantity = data["quantity"]
    if data.get("unit"):
        item.unit = normalize_unit(data["unit"])
    if "category" in data:
        item.category = data["category"]
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.InventoryItem, item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()


# --------------------------------------------------------------------------- #
# Photo extraction
# --------------------------------------------------------------------------- #
@router.post("/extract", response_model=schemas.ExtractionResult)
async def extract(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a fridge/pantry photo; returns proposed items (NOT yet saved)."""
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image too large (max 12 MB).")

    try:
        image_path, data_url = preprocess_and_save(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not read that image: {exc}")

    batch = models.ExtractionBatch(image_path=image_path, status="pending_review")
    db.add(batch)
    db.commit()
    db.refresh(batch)

    try:
        items, raw_response = extract_items(data_url)
    except Exception as exc:  # noqa: BLE001
        batch.status = "discarded"
        db.commit()
        raise HTTPException(502, f"AI extraction failed: {exc}")

    batch.raw_ai_response = raw_response
    db.commit()

    return schemas.ExtractionResult(
        batch_id=batch.id,
        image_url=f"/api/inventory/extract/{batch.id}/image",
        status=batch.status,
        items=items,
    )


@router.get("/extract/{batch_id}", response_model=schemas.ExtractionResult)
def get_extraction(batch_id: int, db: Session = Depends(get_db)):
    """Re-fetch a pending extraction (so a review can be resumed)."""
    batch = db.get(models.ExtractionBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Extraction batch not found")
    return schemas.ExtractionResult(
        batch_id=batch.id,
        image_url=f"/api/inventory/extract/{batch.id}/image",
        status=batch.status,
        items=parse_items(batch.raw_ai_response or {}),
    )


@router.get("/extract/{batch_id}/image")
def get_extraction_image(batch_id: int, db: Session = Depends(get_db)):
    batch = db.get(models.ExtractionBatch, batch_id)
    if batch is None or not os.path.exists(batch.image_path):
        raise HTTPException(404, "Image not found")
    return FileResponse(batch.image_path, media_type="image/jpeg")


@router.post(
    "/extract/{batch_id}/confirm",
    response_model=list[schemas.InventoryItemOut],
)
def confirm_extraction(
    batch_id: int,
    payload: schemas.ConfirmExtractionRequest,
    db: Session = Depends(get_db),
):
    """Persist the user-reviewed item list into inventory."""
    batch = db.get(models.ExtractionBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Extraction batch not found")

    created: list[models.InventoryItem] = []
    for it in payload.items:
        if not it.name.strip():
            continue
        item = models.InventoryItem(
            name=it.name.strip().lower(),
            quantity=it.quantity,
            unit=normalize_unit(it.unit),
            category=it.category,
            source="photo",
            extraction_batch_id=batch.id,
        )
        db.add(item)
        created.append(item)

    batch.status = "confirmed"
    db.commit()
    for c in created:
        db.refresh(c)
    return created
