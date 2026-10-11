"""Store sections for the shopping list: guessing, overriding, and carrying the
aisle into the fridge when the cart is moved to inventory."""
import pytest

from app import models, schemas
from app.routers import shopping
from app.services.aisles import AISLES, guess_category, normalize_category
from conftest import LOCAL_USER


@pytest.mark.parametrize("name,aisle", [
    ("lemons", "produce"), ("bell pepper", "produce"), ("green onions", "produce"),
    ("chicken thighs", "meat"), ("ground beef", "meat"),
    ("shrimp", "seafood"), ("salmon fillet", "seafood"),
    ("milk", "dairy"), ("Gruyère", "dairy"), ("eggs", "dairy"), ("sour cream", "dairy"),
    ("coconut milk", "pantry"), ("rice", "pantry"), ("olive oil", "pantry"), ("black pepper", "pantry"),
    ("chili flakes", "pantry"), ("red chili pepper", "produce"), ("jalapeños", "produce"),
    ("soy sauce", "condiment"), ("mayo", "condiment"),
    ("frozen peas", "frozen"), ("sourdough bread", "bakery"), ("orange juice", "beverage"),
    ("mystery item", "other"), ("", "other"),
])
def test_guess_category(name, aisle):
    assert guess_category(name) == aisle


def test_aisles_vocabulary_and_normalization():
    assert AISLES[0] == "produce" and AISLES[-1] == "other" and len(set(AISLES)) == len(AISLES)
    assert normalize_category(" Dairy ") == "dairy"
    assert normalize_category("aisle 7") is None


def test_rows_get_an_aisle_on_create_import_and_legacy_read(db):
    row = shopping.add_shopping_item(schemas.ShoppingItemCreate(name="Lemons", quantity=3, unit="piece"), LOCAL_USER, db)
    assert row.category == "produce"
    chosen = shopping.add_shopping_item(schemas.ShoppingItemCreate(name="lemons", category="beverage"), LOCAL_USER, db)
    assert chosen.category == "beverage"
    meal = models.Meal(user_id=LOCAL_USER.id, title="Stir fry", title_normalized="stir fry",
                       recipe_json={"ingredients": [{"name": "soy sauce", "quantity": 2, "unit": "tbsp", "in_stock": False}], "steps": []})
    legacy = models.ShoppingListItem(user_id=LOCAL_USER.id, name="cheddar", unit="oz", category=None)
    db.add_all([meal, legacy]); db.commit()
    imported = shopping.import_meal(meal.id, LOCAL_USER, db)
    assert [(i.name, i.category) for i in imported] == [("soy sauce", "condiment")]
    listed = {r.name: r.category for r in shopping.list_shopping(LOCAL_USER, db)}
    assert listed["cheddar"] == "dairy"


def test_update_can_move_a_row_to_another_aisle(db):
    row = shopping.add_shopping_item(schemas.ShoppingItemCreate(name="tofu"), LOCAL_USER, db)
    assert row.category == "dairy"
    out = shopping.update_shopping_item(row.id, schemas.ShoppingItemUpdate(category="produce"), LOCAL_USER, db)
    assert out.category == "produce"
    out = shopping.update_shopping_item(row.id, schemas.ShoppingItemUpdate(category="not-an-aisle"), LOCAL_USER, db)
    assert out.category == "produce"


def test_checked_items_carry_their_aisle_into_the_fridge(db):
    for name, qty, unit in [("lemons", 3, "piece"), ("frozen peas", 1, "pack"), ("mystery item", None, "unknown")]:
        row = shopping.add_shopping_item(schemas.ShoppingItemCreate(name=name, quantity=qty, unit=unit), LOCAL_USER, db)
        shopping.update_shopping_item(row.id, schemas.ShoppingItemUpdate(checked=True), LOCAL_USER, db)
    created = shopping.checked_to_inventory(LOCAL_USER, db)
    got = {i.name: (i.category, i.storage, i.expires_at) for i in created}
    assert got == {
        "lemons": ("produce", "fridge", None),
        "frozen peas": ("frozen", "freezer", None),
        "mystery item": (None, "pantry", None),
    }
    assert shopping.list_shopping(LOCAL_USER, db) == []
