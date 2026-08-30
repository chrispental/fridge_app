"""Preferences: one row per user, created lazily with defaults."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import CurrentUser
from ..database import get_db
from ..services.scope import get_prefs

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=schemas.PreferencesOut)
def get_preferences(user: CurrentUser, db: Session = Depends(get_db)):
    return get_prefs(db, user.id)


@router.get("/status", response_model=schemas.OnboardStatus)
def onboard_status(user: CurrentUser, db: Session = Depends(get_db)):
    return {"onboarded": get_prefs(db, user.id).onboarded}


@router.put("", response_model=schemas.PreferencesOut)
def update_preferences(
    payload: schemas.PreferencesUpdate, user: CurrentUser, db: Session = Depends(get_db)
):
    prefs = get_prefs(db, user.id)
    for field, value in payload.model_dump().items():
        setattr(prefs, field, value)
    prefs.onboarded = True  # completing the form means onboarding is done
    db.commit()
    db.refresh(prefs)
    return prefs
