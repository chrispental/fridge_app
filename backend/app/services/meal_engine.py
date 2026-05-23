"""Meal suggestion engine: prompt building, AI call, and rule enforcement.

The no-repeat rule and the allergy filter are enforced *server-side* after the
AI responds — the LLM's cooperation is treated as a hint, never a guarantee.
"""
import difflib
import logging
import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..models import utcnow
from ..schemas import MealSuggestion, RecipeIngredient, RecipeSource
from . import brave_search
from .ai_client import call_structured
from .prompts import load_prompt
from .staples import is_staple
from .units import normalize_unit
from .weather import get_weather

logger = logging.getLogger(__name__)

_REPEAT_SIMILARITY = 0.82  # titles at/above this ratio count as the same meal
_GRILL_KEYWORDS = ("grill", "barbecue", "bbq", "broil")
# Grocery/commerce domains we'd rather not use as a "view full recipe" source.
_STORE_DOMAINS = (
    "kroger.com", "walmart.com", "target.com", "instacart.com", "amazon.",
    "doordash.com", "ubereats.com", "grubhub.com", "costco.com", "safeway.com",
    "wholefoodsmarket.com", "wegmans.com", "albertsons.com", "heb.com",
    "publix.com", "samsclub.com", "shipt.com", "freshdirect.com",
)

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
                    "cooking_method": {"type": "string"},
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
                    "cooking_method",
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


def _is_grill(suggestion: MealSuggestion) -> bool:
    """True if the meal is grilled — checks the method field and scans title/steps."""
    method = (suggestion.cooking_method or "").lower()
    if any(kw in method for kw in _GRILL_KEYWORDS):
        return True
    haystack = " ".join([suggestion.title or ""] + list(suggestion.steps)).lower()
    return any(kw in haystack for kw in _GRILL_KEYWORDS)


def _pick_recipe(results: list[dict], avoid_url: str | None = None) -> dict | None:
    """Prefer an actual recipe page over a grocery/store result; fall back to first.

    When `avoid_url` is given (the source used last time this dish was suggested),
    skip it so a re-suggested dish gets a fresh recipe link.
    """
    if not results:
        return None

    def is_store(r: dict) -> bool:
        host = urlparse(r.get("url", "")).netloc.lower()
        return any(store in host for store in _STORE_DOMAINS)

    candidates = [r for r in results if not is_store(r)] or results
    if avoid_url:
        fresh = [r for r in candidates if r.get("url") != avoid_url]
        candidates = fresh or candidates
    return candidates[0]


def _enrich_with_brave(suggestion: MealSuggestion, avoid_url: str | None = None) -> None:
    """Attach a food photo and a 'view full recipe' link via Brave. Fully fail-soft."""
    try:
        query = f"{suggestion.title} recipe"
        suggestion.image_url = brave_search.search_image(query)
        best = _pick_recipe(brave_search.search_web(query, count=5), avoid_url)
        if best:
            suggestion.source = RecipeSource(
                title=best["title"] or suggestion.title,
                url=best["url"],
            )
    except Exception as exc:  # noqa: BLE001 - enrichment must never break suggestion
        logger.warning("Brave enrichment failed for %r: %s", suggestion.title, exc)


def _prior_source_url(db: Session, title_normalized: str) -> str | None:
    """The recipe-source URL used by the most recent earlier meal with this title."""
    row = (
        db.query(models.Meal)
        .filter(models.Meal.title_normalized == title_normalized)
        .order_by(models.Meal.suggested_at.desc())
        .first()
    )
    if row and row.recipe_json:
        return ((row.recipe_json.get("source") or {}) if isinstance(row.recipe_json, dict) else {}).get("url")
    return None


def _recent_feedback(db: Session, limit: int = 12) -> tuple[list[str], list[str]]:
    """Recent post-cook feedback as prompt lines, plus titles of disliked dishes.

    Returns (feedback_lines, disliked_titles). `disliked_titles` are added to the
    do-not-suggest list so meals the user disliked don't come back.
    """
    rows = (
        db.query(models.Meal)
        .filter(models.Meal.feedback_at.isnot(None))
        .order_by(models.Meal.feedback_at.desc())
        .limit(limit)
        .all()
    )
    lines: list[str] = []
    disliked: list[str] = []
    for m in rows:
        rating = m.rating or 0
        parts = []
        if rating > 0:
            parts.append("liked")
        elif rating < 0:
            parts.append("disliked")
        if m.feedback_tags:
            parts.append(", ".join(m.feedback_tags))
        if m.feedback_notes:
            parts.append(f'"{m.feedback_notes}"')
        if parts:
            lines.append(f"- {m.title}: {'; '.join(parts)}")
        if rating < 0:
            disliked.append(m.title)
    return lines, disliked


def most_recent_delivery(db: Session) -> "models.Meal | None":
    """The most recent meal ordered for delivery within the last 7 days, if any."""
    from datetime import timedelta

    cutoff = utcnow() - timedelta(days=7)
    return (
        db.query(models.Meal)
        .filter(models.Meal.delivery_ordered_at >= cutoff)
        .order_by(models.Meal.delivery_ordered_at.desc())
        .first()
    )


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
                cooking_method=str(s.get("cooking_method") or "stovetop").strip().lower(),
                ingredients=ingredients,
                steps=[str(x) for x in s.get("steps", []) if str(x).strip()],
                missing_ingredients=[
                    str(x) for x in s.get("missing_ingredients", []) if str(x).strip()
                ],
            )
        )
    return out


def _annotate_in_stock(suggestion: MealSuggestion, inventory: list, staples: list[str]) -> None:
    """Recompute each ingredient's `in_stock` flag from real inventory (don't trust AI).

    Pantry staples count as in-stock too — they're assumed always on hand.
    """
    inv_names = [i.name.lower().strip() for i in inventory]
    for ing in suggestion.ingredients:
        nm = ing.name.lower().strip()
        ing.in_stock = bool(
            nm
            and (
                any(nm in inv or inv in nm for inv in inv_names if inv)
                or is_staple(nm, staples)
            )
        )


def _shortfall(suggestion: MealSuggestion) -> tuple[int, int]:
    """Sort key: fewer missing ingredients first. Call after `_annotate_in_stock`.

    Meals you can make right now (nothing out of stock) sort to the top; meals that
    need a shopping trip sink to the bottom, ordered by how much they need.
    """
    out_of_stock = sum(1 for ing in suggestion.ingredients if not ing.in_stock)
    return (out_of_stock, len(suggestion.missing_ingredients))


def _build_user_prompt(prefs, inventory, do_not_repeat: list[str], weather=None, idea=None, feedback_lines=None) -> str:
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

    staples = getattr(prefs, "pantry_staples", None) or []

    request_block = (
        f"\nWHAT THE USER WANTS RIGHT NOW (prioritize this strongly): {idea.strip()}\n"
        if idea and idea.strip()
        else ""
    )

    feedback_block = (
        "\nPAST FEEDBACK (tailor to this — honor what they liked, fix complaints such as "
        "reducing salt for 'too salty', and do not repeat disliked dishes):\n"
        + "\n".join(feedback_lines)
        + "\n"
        if feedback_lines
        else ""
    )

    if weather is not None and not weather["grill_ok"]:
        weather_line = (
            f"\nCURRENT WEATHER: {weather['summary']}. "
            "Do NOT suggest grilled / barbecue meals.\n"
        )
    elif weather is not None:
        weather_line = f"\nCURRENT WEATHER: {weather['summary']}.\n"
    else:
        weather_line = ""

    return f"""USER PREFERENCES
Household size: {prefs.household_size}
Allergies (NEVER use these): {joined(prefs.allergies)}
Dietary restrictions: {joined(prefs.dietary_restrictions)}
Equipment available: {joined(prefs.equipment) if prefs.equipment else 'basic stovetop only'}
Maximum complexity (1-5): {prefs.max_complexity}
Disliked ingredients: {joined(prefs.disliked_ingredients)}
Disliked cuisines: {joined(prefs.disliked_cuisines)}
ALWAYS AVAILABLE (assume on hand; mark in_stock and never list as missing): {joined(staples)}
{weather_line}
CURRENT INVENTORY
{inv_text}

DO NOT SUGGEST THESE RECENT MEALS
{dnr}
{feedback_block}{request_block}
Suggest meals I can make right now."""


def _generate(db: Session, prefs, inventory, do_not_repeat, count: int, weather=None, idea=None, feedback_lines=None) -> list[MealSuggestion]:
    system_prompt = load_prompt("suggestion_system.md").replace("{count}", str(count))
    raw = call_structured(
        model=settings.openrouter_meal_model,
        system_prompt=system_prompt,
        user_content=_build_user_prompt(prefs, inventory, do_not_repeat, weather, idea, feedback_lines),
        json_schema=SUGGESTION_SCHEMA,
        schema_name="meal_suggestions",
    )
    return _parse_suggestions(raw)


def suggest_meals(db: Session, count: int = 3, idea: str | None = None) -> list[models.Meal]:
    """Generate meal suggestions, enforce rules, persist them, return Meal rows.

    `idea` is optional free text (ingredients, a craving, a cuisine, a mood) that
    biases the suggestion; None/empty means "surprise me" from inventory + prefs.
    """
    prefs = db.get(models.Preferences, 1)
    inventory = db.query(models.InventoryItem).all()
    recent = _recent_titles(db, prefs.no_repeat_days if prefs else 14)

    # Past feedback steers the prompt; disliked dishes are added to the avoid list
    # so they're filtered out server-side just like recent meals.
    feedback_lines, disliked = _recent_feedback(db)
    avoid = recent + disliked
    avoid_norm = [normalize_title(t) for t in avoid]

    # Grilling is gated on live weather (winter/rain). Skipped when no location is set.
    weather = get_weather(prefs.location) if (prefs and prefs.location) else None
    grill_blocked = weather is not None and not weather["grill_ok"]

    suggestions = _generate(db, prefs, inventory, avoid, count, weather, idea, feedback_lines)

    def keep(s: MealSuggestion) -> bool:
        return (
            not _allergen_violation(s, prefs.allergies)
            and not _is_repeat(s.title, avoid_norm)
            and not (grill_blocked and _is_grill(s))
        )

    safe = [s for s in suggestions if keep(s)]

    # If everything was filtered out, retry once with the rejects also excluded.
    if not safe and suggestions:
        rejected = [s.title for s in suggestions]
        retry = _generate(db, prefs, inventory, avoid + rejected, count, weather, idea, feedback_lines)
        safe = [s for s in retry if keep(s)]

    # Recompute in-stock from real inventory, then order makeable-now meals first.
    staples = (prefs.pantry_staples if prefs else None) or []
    for s in safe:
        _annotate_in_stock(s, inventory, staples)
    safe.sort(key=_shortfall)

    meals: list[models.Meal] = []
    for s in safe:
        # Re-suggested dish? Skip the source it used last time for a fresh recipe.
        _enrich_with_brave(s, _prior_source_url(db, normalize_title(s.title)))
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


def create_plan(db: Session, count: int) -> models.MealPlan:
    """Generate a `count`-meal plan, one slot at a time, reusing suggest_meals.

    Single-meal calls keep each recipe well under the output-token cap and re-read the
    no-repeat window between calls, so the week's meals come out distinct. Slots where
    generation yields nothing are skipped (no gaps in slot_index).
    """
    plan = models.MealPlan()
    db.add(plan)
    db.flush()  # assign plan.id

    slot = 0
    for _ in range(count):
        meals = suggest_meals(db, count=1)
        if not meals:
            continue
        db.add(
            models.MealPlanEntry(plan_id=plan.id, slot_index=slot, meal_id=meals[0].id)
        )
        slot += 1

    db.commit()
    db.refresh(plan)
    return plan


def swap_slot(db: Session, entry: models.MealPlanEntry) -> models.Meal | None:
    """Re-roll one plan slot with a fresh suggestion; returns the new Meal (or None)."""
    meals = suggest_meals(db, count=1)
    if not meals:
        return None
    entry.meal_id = meals[0].id
    db.commit()
    db.refresh(entry)
    return meals[0]
