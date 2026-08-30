"""Per-user scoping helpers — the one place that knows how ownership is enforced.

Routers and the meal engine call these instead of `db.get(Model, id)` /
`db.query(Model).all()`, so a query can't accidentally cross users.
"""
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from .staples import DEFAULT_STAPLES

T = TypeVar("T")


def get_prefs(db: Session, user_id: str) -> models.Preferences:
    """This user's preferences row, created with defaults on first access."""
    prefs = db.query(models.Preferences).filter_by(user_id=user_id).one_or_none()
    if prefs is None:
        prefs = models.Preferences(user_id=user_id, pantry_staples=list(DEFAULT_STAPLES))
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


def staples_for(db: Session, user_id: str) -> list[str]:
    return list(get_prefs(db, user_id).pantry_staples or [])


def inventory_for(db: Session, user_id: str) -> list[models.InventoryItem]:
    return db.query(models.InventoryItem).filter_by(user_id=user_id).all()


def get_owned(db: Session, model: type[T], obj_id: int, user_id: str, *, label: str) -> T:
    """Fetch a row by id, 404-ing if it doesn't exist *or* belongs to someone else
    (404 rather than 403 so ids don't leak across users)."""
    obj = db.get(model, obj_id)
    if obj is None or getattr(obj, "user_id", None) != user_id:
        raise HTTPException(404, f"{label} not found")
    return obj
