"""Tests for the grill/weather gate and the weekly delivery quota."""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.models import utcnow
from app.schemas import MealSuggestion, RecipeIngredient
from app.services import brave_search, meal_engine, weather


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
    monkeypatch.setattr(meal_engine, "_enrich_with_brave", lambda s, avoid_url=None: None)

    meals = meal_engine.suggest_meals(db, count=2)
    titles = [m.title for m in meals]
    assert "Tomato Soup" in titles
    assert "Grilled Steak" not in titles


# --- location-aware delivery headers ----------------------------------------
def test_location_headers_zip():
    h = brave_search._location_headers("06825")
    assert h["X-Loc-Postal-Code"] == "06825"
    assert h["X-Loc-Country"]


def test_location_headers_city_state():
    h = brave_search._location_headers("Austin, TX")
    assert h["X-Loc-City"] == "Austin"
    assert h["X-Loc-State"] == "TX"


def test_location_headers_empty():
    assert brave_search._location_headers("") == {}
    assert brave_search._location_headers(None) == {}


# --- recipe source prefers real recipe sites over stores ---------------------
def test_pick_recipe_skips_store_domain():
    results = [
        {"title": "Kroger", "url": "https://www.kroger.com/r/abc", "description": ""},
        {"title": "AllRecipes", "url": "https://www.allrecipes.com/x", "description": ""},
    ]
    assert meal_engine._pick_recipe(results)["url"] == "https://www.allrecipes.com/x"


def test_pick_recipe_falls_back_when_all_stores():
    results = [{"title": "Kroger", "url": "https://kroger.com/x", "description": ""}]
    assert meal_engine._pick_recipe(results)["url"] == "https://kroger.com/x"
    assert meal_engine._pick_recipe([]) is None


def test_shortfall_orders_makeable_first():
    full = MealSuggestion(
        title="A", ingredients=[RecipeIngredient(name="x", in_stock=True)]
    )
    needs = MealSuggestion(
        title="B",
        ingredients=[
            RecipeIngredient(name="x", in_stock=True),
            RecipeIngredient(name="y", in_stock=False),
        ],
        missing_ingredients=["y"],
    )
    assert meal_engine._shortfall(full) < meal_engine._shortfall(needs)


def test_suggest_meals_puts_in_stock_meals_on_top(db, monkeypatch):
    db.add(models.Preferences(id=1))
    db.add(models.InventoryItem(name="eggs", storage="fridge"))
    db.commit()

    generated = [
        MealSuggestion(
            title="Needs Shopping",
            cooking_method="stovetop",
            ingredients=[RecipeIngredient(name="eggs"), RecipeIngredient(name="caviar")],
            missing_ingredients=["caviar"],
        ),
        MealSuggestion(
            title="All In Stock",
            cooking_method="stovetop",
            ingredients=[RecipeIngredient(name="eggs")],
        ),
    ]
    monkeypatch.setattr(meal_engine, "_generate", lambda *a, **k: list(generated))
    monkeypatch.setattr(meal_engine, "_enrich_with_brave", lambda s, avoid_url=None: None)

    meals = meal_engine.suggest_meals(db, count=5)
    assert [m.title for m in meals] == ["All In Stock", "Needs Shopping"]


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
    monkeypatch.setattr(meal_engine, "_enrich_with_brave", lambda s, avoid_url=None: None)

    meals = meal_engine.suggest_meals(db, count=1)
    assert [m.title for m in meals] == ["Grilled Steak"]


# --- post-cook feedback ------------------------------------------------------
def test_recent_feedback_lines_and_disliked(db):
    db.add(models.Meal(
        title="Salty Stew", title_normalized="salty stew", recipe_json={},
        rating=-1, feedback_tags=["too salty"], feedback_notes="needs less salt",
        feedback_at=utcnow(),
    ))
    db.add(models.Meal(
        title="Great Tacos", title_normalized="great tacos", recipe_json={},
        rating=1, feedback_tags=["loved it"], feedback_at=utcnow(),
    ))
    db.commit()

    lines, disliked = meal_engine._recent_feedback(db)
    joined = "\n".join(lines)
    assert "Salty Stew" in joined and "too salty" in joined and "needs less salt" in joined
    assert "disliked" in joined and "liked" in joined
    assert disliked == ["Salty Stew"]


def test_prior_source_url(db):
    db.add(models.Meal(
        title="Pasta", title_normalized="pasta", suggested_at=utcnow(),
        recipe_json={"source": {"title": "X", "url": "https://a.com/r"}},
    ))
    db.commit()
    assert meal_engine._prior_source_url(db, "pasta") == "https://a.com/r"
    assert meal_engine._prior_source_url(db, "nope") is None


def test_pick_recipe_avoids_prior_source():
    results = [
        {"title": "Old", "url": "https://old.com/r"},
        {"title": "New", "url": "https://new.com/r"},
    ]
    assert meal_engine._pick_recipe(results, "https://old.com/r")["url"] == "https://new.com/r"
    # If the only option is the avoided one, fall back to it rather than nothing.
    assert meal_engine._pick_recipe([results[0]], "https://old.com/r")["url"] == "https://old.com/r"


def test_disliked_dish_is_excluded_from_suggestions(db, monkeypatch):
    db.add(models.Meal(
        title="Mushy Risotto", title_normalized="mushy risotto", recipe_json={},
        rating=-1, feedback_notes="gluey", feedback_at=utcnow(),
    ))
    db.add(models.Preferences(id=1))
    db.commit()

    monkeypatch.setattr(
        meal_engine, "_generate",
        lambda *a, **k: [
            MealSuggestion(title="Mushy Risotto", cooking_method="stovetop"),
            MealSuggestion(title="Fresh Salad", cooking_method="no-cook"),
        ],
    )
    monkeypatch.setattr(meal_engine, "_enrich_with_brave", lambda s, avoid_url=None: None)

    meals = meal_engine.suggest_meals(db, count=2)
    titles = [m.title for m in meals]
    assert "Mushy Risotto" not in titles  # disliked dish filtered out
    assert "Fresh Salad" in titles
