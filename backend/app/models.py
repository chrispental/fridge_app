"""SQLAlchemy ORM models.

Every user-owned table carries a `user_id` (a Supabase Auth `sub` UUID string, or the
fixed local user in single-user mode — see `app/auth.py`). The schema is managed by
Alembic (`backend/alembic/`); on startup the app upgrades to head — see `app/main.py`.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from .database import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (avoids the deprecated `datetime.utcnow`)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Ownership column shared by every user-scoped table. String(36) (not a native UUID
# type) so SQLite and Postgres store exactly the same thing and Supabase's `sub`
# claim can be used verbatim.
def user_id_column(**kwargs) -> Column:
    return Column(String(36), ForeignKey("users.id"), nullable=False, index=True, **kwargs)


class User(Base):
    """One row per person. `id` is the Supabase Auth user id (`sub`) in cloud mode,
    or `settings.local_user_id` in single-user local mode. Rows are created lazily
    on a user's first authenticated request."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=True)


class Preferences(Base):
    __tablename__ = "preferences"

    id = Column(Integer, primary_key=True)
    user_id = user_id_column(unique=True)  # exactly one preferences row per user
    name = Column(String, default="", nullable=False)  # display name for greetings
    household_size = Column(Integer, default=1, nullable=False)
    allergies = Column(JSON, default=list, nullable=False)
    dietary_restrictions = Column(JSON, default=list, nullable=False)
    equipment = Column(JSON, default=list, nullable=False)
    max_complexity = Column(Integer, default=3, nullable=False)  # 1-5
    disliked_ingredients = Column(JSON, default=list, nullable=False)
    disliked_cuisines = Column(JSON, default=list, nullable=False)
    no_repeat_days = Column(Integer, default=14, nullable=False)
    location = Column(String, default="", nullable=False)  # city/ZIP for weather & delivery
    # Basics assumed always on hand (salt, pepper, ...) — never counted as missing or shopped.
    pantry_staples = Column(JSON, default=list, nullable=False)
    onboarded = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class ExtractionBatch(Base):
    """One row per uploaded fridge/pantry photo (audit + resume-review)."""

    __tablename__ = "extraction_batches"

    id = Column(Integer, primary_key=True)
    user_id = user_id_column()
    image_key = Column(String, nullable=False)  # opaque key for services/blob_storage
    raw_ai_response = Column(JSON, nullable=True)
    status = Column(String, default="pending_review", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    items = relationship("InventoryItem", back_populates="batch")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True)
    user_id = user_id_column()
    name = Column(String, nullable=False)
    quantity = Column(Float, nullable=True)
    unit = Column(String, default="unknown", nullable=False)
    category = Column(String, nullable=True)
    storage = Column(String, default="unsorted", nullable=False)  # fridge|freezer|pantry|counter|unsorted
    image_url = Column(String, nullable=True)  # NULL=not fetched, ""=tried/none, else Brave thumbnail
    source = Column(String, default="manual", nullable=False)  # manual | photo
    expires_at = Column(Date, nullable=True)  # best-before; NULL = unknown/not tracked
    extraction_batch_id = Column(
        Integer, ForeignKey("extraction_batches.id"), nullable=True
    )
    added_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    batch = relationship("ExtractionBatch", back_populates="items")


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True)
    user_id = user_id_column()
    title = Column(String, nullable=False)
    title_normalized = Column(String, index=True, nullable=False)
    cuisine = Column(String, nullable=True)
    recipe_json = Column(JSON, nullable=False)  # full MealSuggestion payload
    status = Column(String, default="suggested", nullable=False)  # suggested | cooked | ordered
    suggested_at = Column(DateTime, default=utcnow, nullable=False)
    cooked_at = Column(DateTime, nullable=True)
    delivery_ordered_at = Column(DateTime, nullable=True)  # set when ordered for delivery
    # Post-cook feedback: rating 1=liked / -1=disliked / NULL=none; tags like "too salty".
    rating = Column(Integer, nullable=True)
    feedback_tags = Column(JSON, nullable=True)
    feedback_notes = Column(String, nullable=True)
    feedback_at = Column(DateTime, nullable=True)


class ShoppingListItem(Base):
    """Standalone shopping list (not tied to a plan). Items arrive manually or are
    imported from a plan's to-buy list / a meal's missing ingredients; checked items
    can be converted into inventory in one call."""

    __tablename__ = "shopping_list_items"

    id = Column(Integer, primary_key=True)
    user_id = user_id_column()
    name = Column(String, nullable=False)  # stored lowercased, like inventory
    quantity = Column(Float, nullable=True)
    unit = Column(String, default="unknown", nullable=False)
    checked = Column(Boolean, default=False, nullable=False)
    source = Column(String, default="manual", nullable=False)  # manual | plan | meal
    created_at = Column(DateTime, default=utcnow, nullable=False)
    checked_at = Column(DateTime, nullable=True)


class MealPlan(Base):
    """A planned week: a thin grouping of N Meal rows via MealPlanEntry slots."""

    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True)
    user_id = user_id_column()
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    entries = relationship(
        "MealPlanEntry",
        back_populates="plan",
        order_by="MealPlanEntry.slot_index",
        cascade="all, delete-orphan",
    )


class MealPlanEntry(Base):
    """One slot in a plan, pointing at a Meal. Swapping a day repoints `meal_id`.
    Ownership is checked on the parent plan, so there is no `user_id` here."""

    __tablename__ = "meal_plan_entries"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("meal_plans.id"), nullable=False)
    slot_index = Column(Integer, nullable=False)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    plan = relationship("MealPlan", back_populates="entries")
    meal = relationship("Meal")
