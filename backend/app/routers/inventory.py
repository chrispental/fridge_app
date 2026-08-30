"""Inventory CRUD + photo-based extraction (extract -> review -> confirm)."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import CurrentUser
from ..database import get_db
from ..services import brave_search
from ..services.blob_storage import get_blob_storage
from ..services.scope import get_owned
from ..services.storage import normalize_storage
from ..services.units import normalize_unit
from ..services.vision import extract_items, parse_items, preprocess

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

MAX_UPLOAD_BYTES = 12 * 1024 * 1024  # 12 MB
MAX_IMAGE_BACKFILL = 100  # cap Brave calls per backfill request


def _owned_item(db: Session, item_id: int, user_id: str) -> models.InventoryItem:
    return get_owned(db, models.InventoryItem, item_id, user_id, label="Item")


def _owned_batch(db: Session, batch_id: int, user_id: str) -> models.ExtractionBatch:
    return get_owned(db, models.ExtractionBatch, batch_id, user_id, label="Extraction batch")


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
@router.get("", response_model=list[schemas.InventoryItemOut])
def list_inventory(
    user: CurrentUser, category: str | None = None, db: Session = Depends(get_db)
):
    query = db.query(models.InventoryItem).filter(models.InventoryItem.user_id == user.id)
    if category:
        query = query.filter(models.InventoryItem.category == category)
    return query.order_by(models.InventoryItem.added_at.desc()).all()


@router.post("", response_model=schemas.InventoryItemOut, status_code=201)
def add_item(
    payload: schemas.InventoryItemCreate, user: CurrentUser, db: Session = Depends(get_db)
):
    item = models.InventoryItem(
        user_id=user.id,
        name=payload.name.strip().lower(),
        quantity=payload.quantity,
        unit=normalize_unit(payload.unit),
        category=payload.category,
        storage=normalize_storage(payload.storage),
        expires_at=payload.expires_at,
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
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    item = _owned_item(db, item_id, user.id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("name"):
        item.name = data["name"].strip().lower()
    if "quantity" in data:
        item.quantity = data["quantity"]
    if data.get("unit"):
        item.unit = normalize_unit(data["unit"])
    if "category" in data:
        item.category = data["category"]
    if data.get("storage"):
        item.storage = normalize_storage(data["storage"])
    if "expires_at" in data:  # key-presence check so it can be cleared to null
        item.expires_at = data["expires_at"]
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    item = _owned_item(db, item_id, user.id)
    db.delete(item)
    db.commit()


@router.post("/backfill-images", response_model=list[schemas.InventoryItemOut])
def backfill_images(user: CurrentUser, db: Session = Depends(get_db)):
    """Fetch a Brave thumbnail for items that don't have one yet (image_url IS NULL).

    Each item is attempted once: stores the URL when found, or "" to record the
    attempt so it isn't refetched. Fail-soft — a Brave outage just leaves "".
    """
    pending = (
        db.query(models.InventoryItem)
        .filter(
            models.InventoryItem.user_id == user.id,
            models.InventoryItem.image_url.is_(None),
        )
        .limit(MAX_IMAGE_BACKFILL)
        .all()
    )
    for item in pending:
        item.image_url = brave_search.search_image(item.name) or ""
    db.commit()
    for item in pending:
        db.refresh(item)
    return pending


# --------------------------------------------------------------------------- #
# Photo extraction
# --------------------------------------------------------------------------- #
@router.post("/extract", response_model=schemas.ExtractionResult)
async def extract(
    user: CurrentUser, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Upload a fridge/pantry photo; returns proposed items (NOT yet saved)."""
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image too large (max 12 MB).")

    try:
        jpeg, data_url = preprocess(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not read that image: {exc}")

    try:
        image_key = get_blob_storage().save_image(jpeg, user_id=user.id)
    except Exception as exc:  # noqa: BLE001 — storage is not fail-soft (see blob_storage)
        raise HTTPException(502, f"Could not store the photo: {exc}")

    batch = models.ExtractionBatch(
        user_id=user.id, image_key=image_key, status="pending_review"
    )
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
def get_extraction(batch_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """Re-fetch a pending extraction (so a review can be resumed)."""
    batch = _owned_batch(db, batch_id, user.id)
    return schemas.ExtractionResult(
        batch_id=batch.id,
        image_url=f"/api/inventory/extract/{batch.id}/image",
        status=batch.status,
        items=parse_items(batch.raw_ai_response or {}),
    )


@router.get("/extract/{batch_id}/image")
def get_extraction_image(batch_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """The photo behind a batch: a redirect to a short-lived signed URL when the
    storage backend can mint one (Supabase), otherwise streamed from the backend."""
    batch = _owned_batch(db, batch_id, user.id)
    blob = get_blob_storage()
    url = blob.signed_url(batch.image_key)
    if url:
        return RedirectResponse(url, status_code=302)
    data = blob.load_image(batch.image_key)
    if data is None:
        raise HTTPException(404, "Image not found")
    return Response(content=data, media_type="image/jpeg")


@router.post(
    "/extract/{batch_id}/confirm",
    response_model=list[schemas.InventoryItemOut],
)
def confirm_extraction(
    batch_id: int,
    payload: schemas.ConfirmExtractionRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Persist the user-reviewed item list into inventory."""
    batch = _owned_batch(db, batch_id, user.id)

    created: list[models.InventoryItem] = []
    for it in payload.items:
        if not it.name.strip():
            continue
        item = models.InventoryItem(
            user_id=user.id,
            name=it.name.strip().lower(),
            quantity=it.quantity,
            unit=normalize_unit(it.unit),
            category=it.category,
            storage=normalize_storage(it.storage),
            expires_at=it.expires_at,
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
