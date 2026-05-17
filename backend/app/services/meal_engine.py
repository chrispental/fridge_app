"""Meal suggestion engine: prompt building, AI call, and rule enforcement.

The no-repeat rule and the allergy filter are enforced *server-side* after the
AI responds — the LLM's cooperation is treated as a hint, never a guarantee.
"""
import difflib
import re

from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..models import utcnow
from ..schemas import MealSuggestion, RecipeIngredient
from .ai_client import call_structured
from .prompts import load_prompt
from .units import normalize_unit

_REPEAT_SIMILARITY = 0.82  # titles at/above this ratio count as the same meal

SUGGESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "cuisine": {"type": "string"},
                    "complexity": {"type": "integer"},
                    "estimated_time_minutes": {"type": "integer"},
                    "servings": {"type": "integer"},
                    "ingredients": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "quantity": {"type": ["number", "null"]},
                                "unit": {"type": "string"},
                                "in_stock": {"type": "boolean"},
                            },
                            "required": ["name", "quantity", "unit", "in_stock"],
                            "additionalProperties": False,
                        },
                    },
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "missing_ingredients": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "title",
                    "cuisine",
                    "complexity",
                    "estimated_time_minutes",
                    "servings",
                    "ingredients",
                    "steps",
                    "missing_ingredients",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for repeat matching."""
    t = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def _is_repeat(title: str, recent_normalized: list[str]) -> bool:
    """True if `title` matches (exactly or fuzzily) a recently used title."""
    norm = normalize_title(title)
    if not norm:
        return False
    for recent in recent_normalized:
        if not recent:
            continue
        if norm == recent:
            return True
        if difflib.SequenceMatcher(None, norm, recent).ratio() >= _REPEAT_SIMILARITY:
            return True
    return False


def _allergen_violation(suggestion: MealSuggestion, allergies: list[str]) -> bool:
    """True if any allergen string appears anywhere in the suggestion."""
    allergens = [a.lower().strip() for a in allergies if a and a.strip()]
    if not allergens:
        return False
    haystack = " ".join(
        [suggestion.title or ""]
        + [i.name for i in suggestion.ingredients]
        + list(suggestion.missing_ingredients)
        + list(suggestion.steps)
    ).lower()
    return any(allergen in haystack for allergen in allergens)


def _recent_titles(db: Session, no_repeat_days: int) -> list[str]:
    """Titles of meals suggested or cooked within the no-repeat window."""
    if no_repeat_days <= 0:
        return []
    from datetime import timedelta

    cutoff = utcnow() - timedelta(days=no_repeat_days)
    rows = (
        db.query(models.Meal)
        .filter(
            (models.Meal.suggested_at >= cutoff)
            | (models.Meal.cooked_at >= cutoff)
        )
        .all()
    )
    return [r.title for r in rows]


def _parse_suggestions(raw: dict) -> list[MealSuggestion]:
    """Coerce a raw AI response into validated MealSuggestion objects."""
    out: list[MealSuggestion] = []
    for s in (raw or {}).get("suggestions", []):
        title = str(s.get("title", "")).strip()
        if not title:
            continue
        ingredients = [
            RecipeIngredient(
                name=str(ing.get("name", "")).strip(),
                quantity=ing.get("quantity"),
                unit=normalize_unit(ing.get("unit")),
                in_stock=bool(ing.get("in_stock", False)),
            )
            for ing in s.get("ingredients", [])
            if str(ing.get("name", "")).strip()
        ]
        try:
            complexity = int(s.get("complexity", 3) or 3)
        except (TypeError, ValueError):
            complexity = 3
        out.append(
            MealSuggestion(
                title=title,
                cuisine=s.get("cuisine") or None,
                complexity=min(max(complexity, 1), 5),
                estimated_time_minutes=s.get("estimated_time_minutes"),
                servings=s.get("servings"),
                ingredients=ingredients,
                steps=[str(x) for x in s.get("steps", []) if str(x).strip()],
                missing_ingredients=[
                    str(x) for x in s.get("missing_ingredients", []) if str(x).strip()
                ],
            )
        )
    return out


def _annotate_in_stock(suggestion: MealSuggestion, inventory: list) -> None:
    """Recompute each ingredient's `in_stock` flag from real inventory (don't trust AI)."""
    inv_names = [i.name.lower().strip() for i in inventory]
    for ing in suggestion.ingredients:
        nm = ing.name.lower().strip()
        ing.in_stock = bool(
            nm and any(nm in inv or inv in nm for inv in inv_names if inv)
        )


def _build_user_prompt(prefs, inventory, do_not_repeat: list[str]) -> str:
    if inventory:
        inv_lines = []
        for i in inventory:
            qty = (
                f"{i.quantity:g} {i.unit}"
                if i.quantity is not None
                else "(amount unknown)"
            )
            inv_lines.append(f"- {i.name}: {qty}")
        inv_text = "\n".join(inv_lines)
    else:
        inv_text = "(inventory is empty)"

    dnr = (
        "\n".join(f"- {t}" for t in do_not_repeat) if do_not_repeat else "(none)"
    )

    def joined(values):
        return ", ".join(values) if values else "none"

    return f"""USER PREFERENCES
Household size: {prefs.household_size}
Allergies (NEVER use these): {joined(prefs.allergies)}
Dietary restrictions: {joined(prefs.dietary_restrictions)}
Equipment available: {joined(prefs.equipment) if prefs.equipment else 'basic stovetop only'}
Maximum complexity (1-5): {prefs.max_complexity}
Disliked ingredients: {joined(prefs.disliked_ingredients)}
Disliked cuisines: {joined(prefs.disliked_cuisines)}

CURRENT INVENTORY
{inv_text}

DO NOT SUGGEST THESE RECENT MEALS
{dnr}

Suggest meals I can make right now."""


def _generate(db: Session, prefs, inventory, do_not_repeat, count: int) -> list[MealSuggestion]:
    system_prompt = load_prompt("suggestion_system.txt").replace("{count}", str(count))
    raw = call_structured(
        model=settings.openrouter_meal_model,
        system_prompt=system_prompt,
        user_content=_build_user_prompt(prefs, inventory, do_not_repeat),
        json_schema=SUGGESTION_SCHEMA,
        schema_name="meal_suggestions",
    )
    return _parse_suggestions(raw)


def suggest_meals(db: Session, count: int = 3) -> list[models.Meal]:
    """Generate meal suggestions, enforce rules, persist them, return Meal rows."""
    prefs = db.get(models.Preferences, 1)
    inventory = db.query(models.InventoryItem).all()
    recent = _recent_titles(db, prefs.no_repeat_days if prefs else 14)
    recent_norm = [normalize_title(t) for t in recent]

    suggestions = _generate(db, prefs, inventory, recent, count)

    def keep(s: MealSuggestion) -> bool:
        return not _allergen_violation(s, prefs.allergies) and not _is_repeat(
            s.title, recent_norm
        )

    safe = [s for s in suggestions if keep(s)]

    # If everything was filtered out, retry once with the rejects also excluded.
    if not safe and suggestions:
        rejected = [s.title for s in suggestions]
        retry = _generate(db, prefs, inventory, recent + rejected, count)
        safe = [s for s in retry if keep(s)]

    meals: list[models.Meal] = []
    for s in safe:
        _annotate_in_stock(s, inventory)
        meal = models.Meal(
            title=s.title,
            title_normalized=normalize_title(s.title),
            cuisine=s.cuisine,
            recipe_json=s.model_dump(),
            status="suggested",
            suggested_at=utcnow(),
        )
        db.add(meal)
        meals.append(meal)

    db.commit()
    for m in meals:
        db.refresh(m)
    return meals
