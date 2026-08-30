from datetime import timedelta

import pytest
from app import models
from conftest import LOCAL_USER
from app.models import utcnow
from app.services.meal_engine import _recent_titles


def _meal(title, days_ago, status="suggested"):
    return models.Meal(user_id=LOCAL_USER.id,
        title=title,
        title_normalized=title.lower(),
        recipe_json={},
        status=status,
        suggested_at=utcnow() - timedelta(days=days_ago),
        cooked_at=(utcnow() - timedelta(days=days_ago)) if status == "cooked" else None,
    )


def test_recent_titles_respects_window(db):
    db.add(_meal("Recent Meal", days_ago=2))
    db.add(_meal("Old Meal", days_ago=40))
    db.commit()

    titles = _recent_titles(db, LOCAL_USER.id, no_repeat_days=14)
    assert "Recent Meal" in titles
    assert "Old Meal" not in titles


def test_recent_titles_includes_cooked(db):
    db.add(_meal("Cooked Recently", days_ago=3, status="cooked"))
    db.commit()
    assert "Cooked Recently" in _recent_titles(db, LOCAL_USER.id, no_repeat_days=14)


def test_no_repeat_window_zero_disables(db):
    db.add(_meal("Whatever", days_ago=0))
    db.commit()
    assert _recent_titles(db, LOCAL_USER.id, no_repeat_days=0) == []
