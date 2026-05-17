"""Pydantic request/response models and AI-output models."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Preferences
# --------------------------------------------------------------------------- #
class PreferencesBase(BaseModel):
    household_size: int = Field(default=1, ge=1, le=20)
    allergies: list[str] = []
    dietary_restrictions: list[str] = []
    equipment: list[str] = []
    max_complexity: int = Field(default=3, ge=1, le=5)
    disliked_ingredients: list[str] = []
    disliked_cuisines: list[str] = []
    no_repeat_days: int = Field(default=14, ge=0, le=365)


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


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    category: str | None = None


class InventoryItemOut(InventoryItemBase):
    id: int
    source: str
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


class MealSuggestion(BaseModel):
    title: str
    cuisine: str | None = None
    complexity: int = 3
    estimated_time_minutes: int | None = None
    servings: int | None = None
    ingredients: list[RecipeIngredient] = []
    steps: list[str] = []
    missing_ingredients: list[str] = []


class MealOut(BaseModel):
    id: int
    title: str
    cuisine: str | None = None
    recipe_json: dict
    status: str
    suggested_at: datetime
    cooked_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class CookRequest(BaseModel):
    decrement_inventory: bool = False
