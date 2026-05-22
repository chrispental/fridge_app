"""Tests for the grill/weather gate and the weekly delivery quota."""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.models import utcnow
from app.schemas import MealSuggestion
from app.services import meal_engine, weather


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


# --- grill detection ---------------------------------------------------------
def test_is_grill_from_method():
    assert meal_engine._is_grill(MealSuggestion(title="Veg Skewers", cooking_method="grill"))
    assert meal_engine._is_grill(MealSuggestion(title="Ribs", cooking_method="barbecue"))


def test_is_grill_from_title_or_steps():
    assert meal_engine._is_grill(
        MealSuggestion(title="Grilled Cheese", cooking_method="stovetop")
    )
    assert meal_engine._is_grill(
        MealSuggestion(title="Chicken", cooking_method="oven", steps=["Broil 10 min"])
    )


def test_not_grill():
    assert not meal_engine._is_grill(
        MealSuggestion(title="Tomato Soup", cooking_method="stovetop", steps=["Simmer"])
    )


# --- weather snippet parsing -------------------------------------------------
def test_snippet_mentions_rain_positive():
    assert weather.snippet_mentions_rain("Showers expected this afternoon")
    assert weather.snippet_mentions_rain("Thunderstorm likely, 80% precipitation")


def test_snippet_mentions_rain_handles_negation():
    assert not weather.snippet_mentions_rain("No rain today, clear skies")
    assert not weather.snippet_mentions_rain("0% chance of rain")


def test_snippet_mentions_rain_empty():
    assert not weather.snippet_mentions_rain("")
    assert not weather.snippet_mentions_rain("Sunny and 75 degrees")


def test_is_winter():
    assert weather.is_winter(1) and weather.is_winter(12)
    assert not weather.is_winter(5) and not weather.is_winter(7)


# --- delivery quota ----------------------------------------------------------
def _meal(title, status="suggested", delivered_days_ago=None):
    return models.Meal(
        title=title,
        title_normalized=title.lower(),
        recipe_json={},
        status=status,
        suggested_at=utcnow(),
        delivery_ordered_at=(
            utcnow() - timedelta(days=delivered_days_ago)
            if delivered_days_ago is not None
            else None
        ),
    )


def test_no_delivery_yet(db):
    db.add(_meal("Pizza"))
    db.commit()
    assert meal_engine.most_recent_delivery(db) is None


def test_recent_delivery_blocks(db):
    db.add(_meal("Sushi", status="ordered", delivered_days_ago=2))
    db.commit()
    assert meal_engine.most_recent_delivery(db) is not None


def test_old_delivery_does_not_block(db):
    db.add(_meal("Sushi", status="ordered", delivered_days_ago=10))
    db.commit()
    assert meal_engine.most_recent_delivery(db) is None


# --- end-to-end grill exclusion through suggest_meals ------------------------
def test_suggest_meals_excludes_grill_in_bad_weather(db, monkeypatch):
    db.add(models.Preferences(id=1, location="Anywhere"))
    db.commit()

    generated = [
        MealSuggestion(title="Grilled Steak", cooking_method="grill"),
        MealSuggestion(title="Tomato Soup", cooking_method="stovetop"),
    ]
    monkeypatch.setattr(meal_engine, "_generate", lambda *a, **k: list(generated))
    monkeypatch.setattr(
        meal_engine, "get_weather",
        lambda loc: {"is_raining": True, "season": "non-winter",
                     "grill_ok": False, "summary": "rain"},
    )
    monkeypatch.setattr(meal_engine, "_enrich_with_brave", lambda s: None)

    meals = meal_engine.suggest_meals(db, count=2)
    titles = [m.title for m in meals]
    assert "Tomato Soup" in titles
    assert "Grilled Steak" not in titles


def test_suggest_meals_allows_grill_in_good_weather(db, monkeypatch):
    db.add(models.Preferences(id=1, location="Anywhere"))
    db.commit()

    monkeypatch.setattr(
        meal_engine, "_generate",
        lambda *a, **k: [MealSuggestion(title="Grilled Steak", cooking_method="grill")],
    )
    monkeypatch.setattr(
        meal_engine, "get_weather",
        lambda loc: {"is_raining": False, "season": "non-winter",
                     "grill_ok": True, "summary": "clear"},
    )
    monkeypatch.setattr(meal_engine, "_enrich_with_brave", lambda s: None)

    meals = meal_engine.suggest_meals(db, count=1)
    assert [m.title for m in meals] == ["Grilled Steak"]
