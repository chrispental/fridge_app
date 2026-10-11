"""The data export contains only the user's own rows, in a stable shape."""
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.routers.export import EXPORT_FORMAT, build_export
from conftest import LOCAL_USER, OTHER_USER


def _seed(db):
    db.add(models.Preferences(user_id=LOCAL_USER.id, name="Chris", household_size=3, allergies=["peanut"], onboarded=True))
    db.add(models.InventoryItem(user_id=LOCAL_USER.id, name="lemons", quantity=3, unit="piece", category="produce", expires_at=date(2026, 10, 20)))
    db.add(models.InventoryItem(user_id=OTHER_USER.id, name="secret sauce", unit="bottle"))
    mine = models.Meal(user_id=LOCAL_USER.id, title="Lemon Chicken", title_normalized="lemon chicken", status="saved", favorite=True,
                       recipe_json={"steps": ["Roast."], "ingredients": []})
    theirs = models.Meal(user_id=OTHER_USER.id, title="Theirs", title_normalized="theirs", recipe_json={})
    db.add_all([mine, theirs]); db.flush()
    plan = models.MealPlan(user_id=LOCAL_USER.id, status="ready", requested_count=1, servings=4, start_date=date(2026, 10, 12))
    plan.entries = [models.MealPlanEntry(slot_index=0, meal_id=mine.id)]
    db.add(plan)
    db.add(models.ShoppingListItem(user_id=LOCAL_USER.id, name="rice", unit="lb", quantity=2, category="pantry"))
    db.add(models.ShoppingListItem(user_id=OTHER_USER.id, name="theirs", unit="unknown"))
    db.add(models.ExtractionBatch(user_id=LOCAL_USER.id, image_key="x.jpg", status="confirmed"))
    db.commit()
    return mine, plan


def test_export_is_scoped_to_the_user_and_complete(db):
    mine, plan = _seed(db)
    out = build_export(db, LOCAL_USER.id)
    assert out["format"] == EXPORT_FORMAT and out["exported_at"]
    assert out["preferences"]["name"] == "Chris" and out["preferences"]["allergies"] == ["peanut"]
    assert "id" not in out["preferences"]
    assert [i["name"] for i in out["inventory"]] == ["lemons"]
    assert out["inventory"][0]["expires_at"] == date(2026, 10, 20) and "image_url" not in out["inventory"][0]
    assert [m["title"] for m in out["meals"]] == ["Lemon Chicken"]
    assert out["meals"][0]["favorite"] is True and out["meals"][0]["recipe_json"]["steps"] == ["Roast."]
    assert out["plans"] == [{"id": plan.id, "created_at": plan.created_at, "status": "ready", "requested_count": 1,
                             "servings": 4, "start_date": date(2026, 10, 12), "meal_ids": [mine.id]}]
    assert [s["name"] for s in out["shopping_list"]] == ["rice"]
    assert out["scans"][0]["status"] == "confirmed" and "image_key" not in out["scans"][0]
    other = build_export(db, OTHER_USER.id)
    assert [i["name"] for i in other["inventory"]] == ["secret sauce"] and other["plans"] == []


def test_export_downloads_as_a_dated_json_file(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'export.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        db.add_all([models.User(id=LOCAL_USER.id), models.User(id=OTHER_USER.id)]); db.commit()
        _seed(db)
    def provide_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = provide_db
    app.dependency_overrides[get_current_user] = lambda: LOCAL_USER
    # No lifespan (like the other HTTP fixtures): the module-level engine is not ours.
    client = TestClient(app)
    try:
        res = client.get("/api/export")
        assert res.status_code == 200
        assert res.headers["content-disposition"].startswith('attachment; filename="fridge-chef-export-')
        body = res.json()
        assert body["format"] == EXPORT_FORMAT
        assert body["inventory"][0]["expires_at"] == "2026-10-20"
        assert body["meals"][0]["title"] == "Lemon Chicken"
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()
