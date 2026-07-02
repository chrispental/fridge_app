"""Pydantic request/response models and AI-output models."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Preferences
# --------------------------------------------------------------------------- #
class PreferencesBase(BaseModel):
    name: str = ""  # display name used for greetings around the app
    household_size: int = Field(default=1, ge=1, le=20)
    allergies: list[str] = []
    dietary_restrictions: list[str] = []
    equipment: list[str] = []
    max_complexity: int = Field(default=3, ge=1, le=5)
    disliked_ingredients: list[str] = []
    disliked_cuisines: list[str] = []
    no_repeat_days: int = Field(default=14, ge=0, le=365)
    location: str = ""  # city or ZIP — used for grilling-weather and delivery lookups
    pantry_staples: list[str] = []  # basics assumed always on hand (salt, pepper, ...)


class PreferencesUpdate(PreferencesBase):
    """Full replacement of preferences (the onboarding/settings form sends all fields)."""


class PreferencesOut(PreferencesBase):
    id: int
    onboarded: bool
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class OnboardStatus(BaseModel):
    onboarded: bool


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #
class InventoryItemBase(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = "unknown"
    category: str | None = None
    storage: str = "unsorted"
    expires_at: date | None = None


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    category: str | None = None
    storage: str | None = None
    expires_at: date | None = None


class InventoryItemOut(InventoryItemBase):
    id: int
    source: str
    image_url: str | None = None
    extraction_batch_id: int | None = None
    added_at: datetime
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Photo extraction
# --------------------------------------------------------------------------- #
class ExtractedItem(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = "unknown"
    category: str | None = None
    storage: str = "unsorted"
    expires_at: date | None = None  # heuristic prefill — the user reviews it
    confidence: float = Field(default=0.5, ge=0, le=1)


class ExtractionResult(BaseModel):
    batch_id: int
    image_url: str
    status: str
    items: list[ExtractedItem]


class ConfirmExtractionRequest(BaseModel):
    items: list[InventoryItemCreate]


# --------------------------------------------------------------------------- #
# Meals
# --------------------------------------------------------------------------- #
class RecipeIngredient(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = "unknown"
    in_stock: bool = False


class RecipeSource(BaseModel):
    title: str
    url: str


class MealSuggestion(BaseModel):
    title: str
    cuisine: str | None = None
    complexity: int = 3
    estimated_time_minutes: int | None = None
    servings: int | None = None
    cooking_method: str = "stovetop"
    ingredients: list[RecipeIngredient] = []
    steps: list[str] = []
    missing_ingredients: list[str] = []
    image_url: str | None = None  # Brave Image Search result (may be absent)
    source: RecipeSource | None = None  # Brave web result: "view full recipe" link


class MealOut(BaseModel):
    id: int
    title: str
    cuisine: str | None = None
    recipe_json: dict
    status: str
    suggested_at: datetime
    cooked_at: datetime | None = None
    delivery_ordered_at: datetime | None = None
    rating: int | None = None  # 1 = liked, -1 = disliked, None = no feedback
    feedback_tags: list[str] | None = None
    feedback_notes: str | None = None
    feedback_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class FeedbackRequest(BaseModel):
    rating: int | None = None  # 1 = liked, -1 = disliked, None = clears the rating
    tags: list[str] = []
    notes: str | None = None


class SuggestRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=5)
    idea: str | None = None  # free text: ingredients, a craving, a cuisine; None = surprise me


class CookRequest(BaseModel):
    decrement_inventory: bool = False


class DeliveryStatusOut(BaseModel):
    used: bool
    remaining: int
    next_available_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Weekly meal plan + shopping list
# --------------------------------------------------------------------------- #
class CreatePlanRequest(BaseModel):
    count: int = Field(default=7, ge=1, le=14)


class MealPlanEntryOut(BaseModel):
    slot_index: int
    meal: MealOut
    model_config = ConfigDict(from_attributes=True)


class MealPlanOut(BaseModel):
    id: int
    created_at: datetime
    entries: list[MealPlanEntryOut]
    model_config = ConfigDict(from_attributes=True)


class ShoppingListItem(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = "unknown"


class ShoppingListOut(BaseModel):
    to_buy: list[ShoppingListItem]
    have: list[ShoppingListItem]
    staples_assumed: list[str]


# --------------------------------------------------------------------------- #
# Standalone shopping list (the shopping_list_items table)
# --------------------------------------------------------------------------- #
class ShoppingItemCreate(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = "unknown"


class ShoppingItemUpdate(BaseModel):
    name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    checked: bool | None = None


class ShoppingItemOut(BaseModel):
    id: int
    name: str
    quantity: float | None = None
    unit: str
    checked: bool
    source: str
    created_at: datetime
    checked_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Meal history stats (the /meals/stats endpoint)
# --------------------------------------------------------------------------- #
class StatsTotals(BaseModel):
    total: int
    suggested: int
    cooked: int
    ordered: int


class TopRatedMeal(BaseModel):
    id: int
    title: str
    cooked_at: datetime | None = None


class CuisineCount(BaseModel):
    cuisine: str
    count: int


class WeekCount(BaseModel):
    week_start: date
    count: int


class IngredientCount(BaseModel):
    name: str
    count: int


class TagCount(BaseModel):
    tag: str
    count: int


class MealStatsOut(BaseModel):
    totals: StatsTotals
    top_rated: list[TopRatedMeal]
    cuisines: list[CuisineCount]
    cooks_per_week: list[WeekCount]
    top_ingredients: list[IngredientCount]
    feedback_tags: list[TagCount]
