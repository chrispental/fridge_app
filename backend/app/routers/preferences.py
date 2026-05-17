"""Preferences: a single singleton row (id=1)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


def get_or_create_prefs(db: Session) -> models.Preferences:
    prefs = db.get(models.Preferences, 1)
    if prefs is None:
        prefs = models.Preferences(id=1)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.get("", response_model=schemas.PreferencesOut)
def get_preferences(db: Session = Depends(get_db)):
    return get_or_create_prefs(db)


@router.get("/status", response_model=schemas.OnboardStatus)
def onboard_status(db: Session = Depends(get_db)):
    return {"onboarded": get_or_create_prefs(db).onboarded}


@router.put("", response_model=schemas.PreferencesOut)
def update_preferences(
    payload: schemas.PreferencesUpdate, db: Session = Depends(get_db)
):
    prefs = get_or_create_prefs(db)
    for field, value in payload.model_dump().items():
        setattr(prefs, field, value)
    prefs.onboarded = True  # completing the form means onboarding is done
    db.commit()
    db.refresh(prefs)
    return prefs
