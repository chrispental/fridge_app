"""Approximate per-serving nutrition for a recipe.

Suggestion, adjustment and AI import ask the meal model for the estimate in the
same call (see the `nutrition` field of SUGGESTION_SCHEMA). This module handles
the remaining cases: meals from before the field existed and recipes imported
from structured data without it, via `POST /meals/{id}/nutrition`. Every value
is labelled an estimate in the UI; schema.org data is labelled "from the recipe".
"""
import json
import re

from ..config import settings
from ..schemas import Nutrition
from .ai_client import call_structured
from .prompts import load_prompt

NUTRITION_FIELDS = {
    "type": "object",
    "properties": {
        "calories": {"type": "integer"},
        "protein_g": {"type": "number"},
        "carbs_g": {"type": "number"},
        "fat_g": {"type": "number"},
    },
    "required": ["calories", "protein_g", "carbs_g", "fat_g"],
    "additionalProperties": False,
}

NUTRITION_SCHEMA = {
    "type": "object",
    "properties": {"nutrition": NUTRITION_FIELDS},
    "required": ["nutrition"],
    "additionalProperties": False,
}

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _number(value, limit: float) -> float | None:
    """A non-negative number from an int/float/'12 g'/'250 calories', else None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = float(value)
    else:
        m = _NUM_RE.search(str(value))
        if not m:
            return None
        n = float(m.group())
    if n < 0 or n > limit or n != n:
        return None
    return n


def parse_nutrition(raw, source: str = "estimate") -> Nutrition | None:
    """Coerce a model or schema.org nutrition object; None when nothing usable."""
    if not isinstance(raw, dict):
        return None
    calories = _number(raw.get("calories"), 5000)
    protein = _number(raw.get("protein_g", raw.get("proteinContent")), 500)
    carbs = _number(raw.get("carbs_g", raw.get("carbohydrateContent")), 1000)
    fat = _number(raw.get("fat_g", raw.get("fatContent")), 500)
    if calories is None and protein is None and carbs is None and fat is None:
        return None
    return Nutrition(
        calories=int(round(calories)) if calories is not None else None,
        protein_g=round(protein, 1) if protein is not None else None,
        carbs_g=round(carbs, 1) if carbs is not None else None,
        fat_g=round(fat, 1) if fat is not None else None,
        source=source,
    )


def estimate_nutrition(recipe: dict) -> Nutrition:
    """Ask the meal model for a per-serving estimate of an existing recipe."""
    keep = ("title", "servings", "ingredients", "steps")
    compact = {k: recipe.get(k) for k in keep}
    compact["ingredients"] = [
        {k: ing.get(k) for k in ("name", "quantity", "unit")}
        for ing in (recipe.get("ingredients") or []) if isinstance(ing, dict)
    ]
    raw = call_structured(
        model=settings.openrouter_meal_model,
        system_prompt=load_prompt("nutrition_system.md"),
        user_content=f"RECIPE (JSON)\n{json.dumps(compact)}\n\nEstimate one serving.",
        json_schema=NUTRITION_SCHEMA,
        schema_name="nutrition_estimate",
        temperature=0.1,
    )
    nutrition = parse_nutrition((raw or {}).get("nutrition"))
    if nutrition is None:
        raise RuntimeError("The chef couldn't estimate nutrition for this recipe. Please try again.")
    return nutrition
