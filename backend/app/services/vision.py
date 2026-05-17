"""Photo -> structured inventory items, via an OpenRouter vision model."""
import base64
import io
import os
import uuid

from PIL import Image

from ..config import settings
from ..schemas import ExtractedItem
from .ai_client import call_structured
from .prompts import load_prompt
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
                    "confidence": {"type": "number"},
                },
                "required": ["name", "quantity", "unit", "category", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def preprocess_and_save(raw_bytes: bytes) -> tuple[str, str]:
    """Downscale + re-encode an uploaded image, persist it, return (path, data_url).

    Downscaling before base64-encoding keeps the request small and cheap.
    """
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    max_dim = settings.max_image_dim
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    jpeg = buf.getvalue()

    os.makedirs(settings.upload_dir, exist_ok=True)
    path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.jpg")
    with open(path, "wb") as fh:
        fh.write(jpeg)

    data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    return path, data_url


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
        items.append(
            ExtractedItem(
                name=name,
                quantity=it.get("quantity"),
                unit=normalize_unit(it.get("unit")),
                category=(it.get("category") or None),
                confidence=min(max(confidence, 0.0), 1.0),
            )
        )
    return items


def extract_items(data_url: str) -> tuple[list[ExtractedItem], dict]:
    """Run vision extraction on an image. Returns (items, raw_ai_response)."""
    raw = call_structured(
        model=settings.openrouter_vision_model,
        system_prompt=load_prompt("extraction_system.txt"),
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
