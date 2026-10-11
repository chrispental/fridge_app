"""Recipe import (JSON-LD and AI fallback), the recipe book, favourites, and
cooking or planning a saved recipe without touching the book entry."""
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.routers import meals, plans
from app.services import meal_engine, recipe_import
from app.services.recipe_import import (
    ImportError_, find_recipe_json_ld, html_to_text, import_recipe, parse_ingredient_line, recipe_from_json_ld,
)
from conftest import LOCAL_USER, OTHER_USER

JSON_LD_PAGE = """<html><head><title>Best Lemon Chicken - Example</title>
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebPage","name":"x"},
{"@type":["Recipe","NewsArticle"],"name":"Lemon &amp; Garlic Chicken","recipeCuisine":"Mediterranean",
"recipeYield":["4 servings"],"prepTime":"PT15M","cookTime":"PT45M",
"recipeIngredient":["1 1/2 lbs chicken thighs, trimmed","2 cloves garlic, minced","½ cup olive oil","200 g spinach","Salt to taste","3 lemons"],
"recipeInstructions":[{"@type":"HowToSection","itemListElement":[{"@type":"HowToStep","text":"Preheat the oven to 400°F."}]},
{"@type":"HowToStep","text":"Roast <b>45 minutes</b>."}]}]}</script></head><body>ignored</body></html>"""


# --- parsing -------------------------------------------------------------------
@pytest.mark.parametrize("line,expected", [
    ("1 1/2 lbs chicken thighs, trimmed", ("chicken thighs", 1.5, "lb")),
    ("½ cup olive oil", ("olive oil", 0.5, "cup")),
    ("2 cloves garlic, minced", ("cloves garlic", 2.0, "piece")),
    ("3 lemons", ("lemons", 3.0, "piece")),
    ("Salt to taste", ("salt to taste", None, "unknown")),
    ("200 g spinach", ("spinach", None, "unknown")),
    ("2-3 tablespoons soy sauce", ("soy sauce", 2.0, "tbsp")),
    ("1 (14 oz) can chickpeas, drained", ("chickpeas", 1.0, "can")),
])
def test_parse_ingredient_line(line, expected):
    ing = parse_ingredient_line(line)
    assert (ing.name, ing.quantity, ing.unit) == expected


def test_json_ld_recipe_is_found_inside_a_graph_and_mapped():
    data = find_recipe_json_ld(JSON_LD_PAGE)
    recipe = recipe_from_json_ld(data, "https://example.com/lemon-chicken")
    assert recipe.title == "Lemon & Garlic Chicken"
    assert recipe.cuisine == "Mediterranean" and recipe.servings == 4
    assert recipe.estimated_time_minutes == 60
    assert [i.name for i in recipe.ingredients][:2] == ["chicken thighs", "cloves garlic"]
    assert recipe.steps == ["Preheat the oven to 400°F.", "Roast 45 minutes."]
    assert recipe.source.url == "https://example.com/lemon-chicken"
    assert find_recipe_json_ld("<html><script type='application/ld+json'>{not json</script></html>") is None


def test_html_to_text_drops_chrome_and_scripts():
    text = html_to_text("<nav>Menu</nav><script>x()</script><h1>Soup</h1><p>Boil &amp; serve.</p>")
    assert "Menu" not in text and "x()" not in text
    assert "Soup" in text and "Boil & serve." in text


def test_import_from_url_prefers_json_ld_without_calling_the_model(monkeypatch):
    monkeypatch.setattr(recipe_import, "fetch_page", lambda url: JSON_LD_PAGE)
    monkeypatch.setattr(recipe_import, "call_structured", lambda **k: (_ for _ in ()).throw(AssertionError("AI called")))
    recipe = import_recipe(url="https://example.com/x")
    assert recipe.title == "Lemon & Garlic Chicken"


def test_import_from_url_falls_back_to_the_model_on_plain_pages(monkeypatch):
    monkeypatch.setattr(recipe_import, "fetch_page", lambda url: "<html><title>Nan's stew</title><body><p>" + "Stew words. " * 20 + "</p></body></html>")
    seen = {}
    def fake(**kwargs):
        seen["text"] = kwargs["user_content"]
        return {"suggestions": [{"title": "Nan's Stew", "servings": 6, "ingredients": [{"name": "beef", "quantity": 1, "unit": "lb", "in_stock": True}], "steps": ["Simmer."], "missing_ingredients": ["x"]}]}
    monkeypatch.setattr(recipe_import, "call_structured", fake)
    recipe = import_recipe(url="https://example.com/stew")
    assert "Stew words" in seen["text"]
    assert recipe.title == "Nan's Stew" and recipe.source.title == "Nan's stew"
    assert recipe.ingredients[0].in_stock is False and recipe.missing_ingredients == []


@pytest.mark.parametrize("url", ["ftp://example.com/x", "http://localhost/x", "http://127.0.0.1/x", "http://10.0.0.5/x"])
def test_private_or_bad_urls_are_refused(url, monkeypatch):
    monkeypatch.setattr(recipe_import.socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, ("10.0.0.5", 80))])
    with pytest.raises(ImportError_):
        recipe_import.fetch_page(url)


def test_import_text_requires_something_to_work_with():
    with pytest.raises(ImportError_):
        import_recipe(text="hi")
    with pytest.raises(ImportError_):
        import_recipe()


# --- routes ----------------------------------------------------------------------
def _saved(db, title="Lemon Chicken", favorite=False):
    row = models.Meal(user_id=LOCAL_USER.id, title=title, title_normalized=meal_engine.normalize_title(title),
                      status="saved", favorite=favorite,
                      recipe_json={"title": title, "servings": 4, "ingredients": [{"name": "chicken", "quantity": 1, "unit": "lb", "in_stock": False}],
                                   "steps": ["Cook."], "missing_ingredients": [], "source": {"title": title, "url": "https://example.com"}})
    db.add(row); db.commit(); db.refresh(row)
    return row


def test_import_route_saves_into_the_book_and_maps_errors(db, monkeypatch):
    monkeypatch.setattr(meals, "import_recipe", lambda **k: recipe_from_json_ld(find_recipe_json_ld(JSON_LD_PAGE), "https://example.com/x"))
    out = meals.import_saved_recipe(schemas.ImportRecipeRequest(url="https://example.com/x"), LOCAL_USER, db)
    assert out.status == "saved" and out.title == "Lemon & Garlic Chicken"
    assert [m.id for m in meals.list_recipes(LOCAL_USER, None, db)] == [out.id]
    assert meals.list_meals(LOCAL_USER, None, None, 50, 0, db) == []  # history excludes the book
    assert [m.id for m in meals.list_meals(LOCAL_USER, "saved", None, 50, 0, db)] == [out.id]
    monkeypatch.setattr(meals, "import_recipe", lambda **k: (_ for _ in ()).throw(ImportError_("nope")))
    with pytest.raises(HTTPException) as exc:
        meals.import_saved_recipe(schemas.ImportRecipeRequest(text="x" * 30), LOCAL_USER, db)
    assert exc.value.status_code == 422


def test_favorite_toggle_and_recipe_book_listing(db):
    cooked = models.Meal(user_id=LOCAL_USER.id, title="Tacos", title_normalized="tacos", status="cooked", recipe_json={})
    db.add(cooked); db.commit()
    assert meals.list_recipes(LOCAL_USER, None, db) == []
    assert meals.set_favorite(cooked.id, schemas.FavoriteRequest(favorite=True), LOCAL_USER, db).favorite is True
    assert [m.title for m in meals.list_recipes(LOCAL_USER, None, db)] == ["Tacos"]
    assert [m.title for m in meals.list_recipes(LOCAL_USER, "tac", db)] == ["Tacos"]
    assert meals.list_recipes(LOCAL_USER, "pizza", db) == []
    with pytest.raises(HTTPException):
        meals.set_favorite(cooked.id, schemas.FavoriteRequest(favorite=True), OTHER_USER, db)


def test_cooking_a_saved_recipe_logs_a_copy_and_keeps_the_book_entry(db):
    saved = _saved(db)
    payload = schemas.CookRequest(decrement_inventory=False, save_leftovers=True, request_id=uuid4())
    logged = meals.cook_meal(saved.id, payload, LOCAL_USER, db)
    replay = meals.cook_meal(saved.id, payload, LOCAL_USER, db)
    assert logged.id != saved.id and logged.status == "cooked" and logged.recipe_json["saved_from"] == saved.id
    assert replay.id == logged.id
    db.refresh(saved)
    assert saved.status == "saved"
    assert db.query(models.Meal).filter_by(user_id=LOCAL_USER.id).count() == 2
    assert db.query(models.InventoryItem).filter_by(source="leftover").count() == 1


def test_saved_recipes_do_not_block_suggestions_but_favourites_are_hinted(db, monkeypatch):
    _saved(db, "Lemon Chicken", favorite=True)
    _saved(db, "Plain Rice")
    assert meal_engine._recent_titles(db, LOCAL_USER.id, 14) == []
    lines = meal_engine._favorite_lines(db, LOCAL_USER.id, [])
    assert lines == ["- Lemon Chicken (chicken)"]
    assert meal_engine._favorite_lines(db, LOCAL_USER.id, ["lemon chicken"]) == []
    prompt = meal_engine._build_user_prompt(
        meal_engine.get_prefs(db, LOCAL_USER.id), [], [], favorite_lines=lines)
    assert "FAVOURITE RECIPES" in prompt and "- Lemon Chicken" in prompt
    assert "FAVOURITE" not in meal_engine._build_user_prompt(meal_engine.get_prefs(db, LOCAL_USER.id), [], [])


def test_add_saved_recipe_to_the_week(db):
    saved = _saved(db)
    out = plans.add_meal(schemas.AddMealToPlanRequest(meal_id=saved.id), LOCAL_USER, db)
    assert out.status == "ready" and len(out.entries) == 1 and out.requested_count == 1
    entry = out.entries[0]
    assert entry.meal.id != saved.id and entry.meal.status == "suggested" and entry.meal.title == "Lemon Chicken"
    out2 = plans.add_meal(schemas.AddMealToPlanRequest(meal_id=saved.id), LOCAL_USER, db)
    assert out2.id == out.id and [e.slot_index for e in out2.entries] == [0, 1]
    db.get(models.MealPlan, out.id).status = "generating"; db.commit()
    with pytest.raises(HTTPException) as exc:
        plans.add_meal(schemas.AddMealToPlanRequest(meal_id=saved.id), LOCAL_USER, db)
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException):
        plans.add_meal(schemas.AddMealToPlanRequest(meal_id=saved.id), OTHER_USER, db)
