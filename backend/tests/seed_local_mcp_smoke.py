"""Create synthetic fixtures ONLY in an empty, disposable local-MCP CI stack."""
import os

from app.config import settings
from app.database import SessionLocal
from app import models

assert os.environ.get("FRIDGE_SYNTHETIC_SMOKE") == "1"
assert settings.mcp_enabled and settings.mcp_mode == "local" and not settings.auth_enabled
assert settings.database_url == "sqlite:////app/data/fridge.db"
with SessionLocal() as db:
    assert db.query(models.MealPlan).count() == 0
    assert db.query(models.InventoryItem).count() == 0
    assert db.query(models.Preferences).count() == 0
    if db.get(models.User, settings.local_user_id) is None:
        db.add(models.User(id=settings.local_user_id))
        db.flush()
    db.add(models.Preferences(user_id=settings.local_user_id, onboarded=True, pantry_staples=[]))
    meal = models.Meal(
        user_id=settings.local_user_id, title="Synthetic rice dinner",
        title_normalized="synthetic rice dinner", status="suggested", favorite=True,
        recipe_json={"ingredients": [{"name": "rice", "quantity": 4, "unit": "cup"}],
                     "steps": ["Cook the rice."]},
    )
    plan = models.MealPlan(user_id=settings.local_user_id, status="ready")
    plan.entries = [models.MealPlanEntry(slot_index=0, meal=meal)]
    db.add(plan)
    db.commit()
print("Synthetic local MCP fixture ready")
