"""Photo -> structured inventory items, via an OpenRouter vision model."""
import base64
import io

from PIL import Image

from ..config import settings
from ..schemas import ExtractedItem
from .ai_client import call_structured
from .expiry import estimate_expiry
from .prompts import load_prompt
from .storage import normalize_storage, storage_from_category
from .units import normalize_unit

# JSON schema for the strict structured-output attempt.
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": ["number", "null"]},
                    "unit": {"type": "string"},
                    "category": {"type": ["string", "null"]},
                    "storage": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                },
                "required": ["name", "quantity", "unit", "category", "storage", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def preprocess(raw_bytes: bytes) -> tuple[bytes, str]:
    """Downscale + re-encode an uploaded image; return (jpeg_bytes, data_url).

    Downscaling before base64-encoding keeps the vision request small and cheap.
    Persisting the bytes is the caller's job (see `services/blob_storage.py`).
    """
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    max_dim = settings.max_image_dim
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    jpeg = buf.getvalue()

    data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    return jpeg, data_url


def parse_items(raw: dict) -> list[ExtractedItem]:
    """Coerce a raw AI response into validated ExtractedItem objects."""
    items: list[ExtractedItem] = []
    for it in (raw or {}).get("items", []):
        name = str(it.get("name", "")).strip().lower()
        if not name:
            continue
        try:
            confidence = float(it.get("confidence", 0.5) or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        category = it.get("category") or None
        # Trust the model's storage guess; fall back to a category-based guess.
        storage = normalize_storage(it.get("storage"))
        if storage == "unsorted":
            storage = storage_from_category(category)
        items.append(
            ExtractedItem(
                name=name,
                quantity=it.get("quantity"),
                unit=normalize_unit(it.get("unit")),
                category=category,
                storage=storage,
                # Heuristic prefill only — the user reviews/edits before confirming.
                expires_at=estimate_expiry(category, storage),
                confidence=min(max(confidence, 0.0), 1.0),
            )
        )
    return items


def extract_items(data_url: str) -> tuple[list[ExtractedItem], dict]:
    """Run vision extraction on an image. Returns (items, raw_ai_response)."""
    raw = call_structured(
        model=settings.openrouter_vision_model,
        system_prompt=load_prompt("extraction_system.md"),
        user_content=[
            {
                "type": "text",
                "text": "Identify the food and grocery items in this fridge/pantry photo.",
            },
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
        json_schema=EXTRACTION_SCHEMA,
        schema_name="inventory_extraction",
    )
    return parse_items(raw), raw
