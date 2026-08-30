"""Tests for the standalone shopping list: merge/dedupe, meal-needs extraction,
checked-to-inventory conversion, and import idempotence (quantities sum)."""
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from conftest import LOCAL_USER
from app.routers import shopping
from app.services.shopping_list import merge_into_list, missing_for_meal


def _db():
    eng = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    models.Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _row(name, unit="unknown", quantity=None, checked=False):
    return SimpleNamespace(name=name, unit=unit, quantity=quantity, checked=checked)


# --- merge_into_list ------------------------------------------------------------
def test_merge_sums_into_existing_open_row():
    existing = [_row("onion", "piece", 2)]
    updated, creates = merge_into_list(existing, [{"name": "Onion", "unit": "piece", "quantity": 3}])
    assert creates == []
    assert updated == [existing[0]]
    assert existing[0].quantity == 5


def test_merge_different_unit_creates_new_row():
    existing = [_row("milk", "quart", 1)]
    updated, creates = merge_into_list(existing, [{"name": "milk", "unit": "cup", "quantity": 2}])
    assert updated == []
    assert [(c["name"], c["unit"], c["quantity"]) for c in creates] == [("milk", "cup", 2)]


def test_merge_never_touches_checked_rows():
    checked = _row("eggs", "dozen", 1, checked=True)
    updated, creates = merge_into_list([checked], [{"name": "eggs", "unit": "dozen", "quantity": 1}])
    assert updated == []
    assert checked.quantity == 1  # untouched
    assert [(c["name"], c["quantity"]) for c in creates] == [("eggs", 1)]


def test_merge_none_quantities_stay_none():
    existing = [_row("basil", "bunch", None)]
    updated, creates = merge_into_list(existing, [{"name": "basil", "unit": "bunch", "quantity": None}])
    assert updated == [] and creates == []  # matched, but nothing to sum
    assert existing[0].quantity is None


def test_merge_dedupes_within_new_items():
    _, creates = merge_into_list(
        [],
        [
            {"name": "carrot", "unit": "piece", "quantity": 2},
            {"name": "Carrot ", "unit": "piece", "quantity": 3},
        ],
    )
    assert [(c["name"], c["quantity"]) for c in creates] == [("carrot", 5)]


def test_merge_skips_blank_names():
    _, creates = merge_into_list([], [{"name": "  ", "unit": "piece", "quantity": 1}])
    assert creates == []


# --- missing_for_meal -------------------------------------------------------------
def _inv(*names):
    return [SimpleNamespace(name=n) for n in names]


def test_missing_for_meal_excludes_in_stock_and_staples():
    recipe = {
        "ingredients": [
            {"name": "chicken", "quantity": 1, "unit": "lb", "in_stock": False},
            {"name": "rice", "quantity": 2, "unit": "cup", "in_stock": False},
            {"name": "salt", "quantity": None, "unit": "unknown", "in_stock": False},
        ],
        "missing_ingredients": [],
    }
    # rice is in inventory (live recompute ignores the stored in_stock flag).
    needed = missing_for_meal(recipe, _inv("rice"), ["salt"])
    assert [n["name"] for n in needed] == ["chicken"]
    assert needed[0]["quantity"] == 1 and needed[0]["unit"] == "lb"


def test_missing_for_meal_adds_uncovered_missing_strings_once():
    recipe = {
        "ingredients": [
            {"name": "chicken", "quantity": 1, "unit": "lb", "in_stock": False},
        ],
        "missing_ingredients": ["chicken", "soy sauce"],
    }
    needed = missing_for_meal(recipe, [], [])
    # "chicken" already covered by the ingredient line; "soy sauce" appended once.
    assert [n["name"] for n in needed] == ["chicken", "soy sauce"]


def test_missing_for_meal_tolerates_empty_recipe():
    assert missing_for_meal({}, [], []) == []


# --- router: checked-to-inventory ---------------------------------------------------
def test_checked_to_inventory_converts_and_removes():
    db = _db()
    db.add(models.ShoppingListItem(user_id=LOCAL_USER.id, name="Lemons", quantity=4, unit="piece", checked=True))
    db.add(models.ShoppingListItem(user_id=LOCAL_USER.id, name="flour", quantity=1, unit="POUND", checked=True))
    db.add(models.ShoppingListItem(user_id=LOCAL_USER.id, name="butter", quantity=1, unit="lb", checked=False))
    db.commit()

    created = shopping.checked_to_inventory(user=LOCAL_USER, db=db)

    by_name = {c.name: c for c in created}
    assert set(by_name) == {"lemons", "flour"}
    assert by_name["flour"].unit == "lb"          # normalized
    assert by_name["lemons"].storage == "unsorted"
    assert by_name["lemons"].source == "manual"

    remaining = db.query(models.ShoppingListItem).all()
    assert [r.name for r in remaining] == ["butter"]  # unchecked row untouched
    assert db.query(models.InventoryItem).count() == 2
    db.close()


# --- router: import idempotence -----------------------------------------------------
def _make_meal(db, title, ingredients):
    meal = models.Meal(user_id=LOCAL_USER.id,
        title=title,
        title_normalized=title.lower(),
        recipe_json={"ingredients": ingredients, "missing_ingredients": []},
        status="suggested",
    )
    db.add(meal)
    db.commit()
    return meal


def test_import_meal_twice_sums_quantities_no_duplicates():
    db = _db()
    db.add(models.Preferences(user_id=LOCAL_USER.id, pantry_staples=["salt"]))
    meal = _make_meal(
        db,
        "Chicken Rice",
        [
            {"name": "chicken", "quantity": 1, "unit": "lb", "in_stock": False},
            {"name": "salt", "quantity": None, "unit": "unknown", "in_stock": False},
        ],
    )

    shopping.import_meal(meal.id, user=LOCAL_USER, db=db)
    shopping.import_meal(meal.id, user=LOCAL_USER, db=db)

    rows = db.query(models.ShoppingListItem).all()
    assert len(rows) == 1  # staple excluded, chicken deduped
    assert rows[0].name == "chicken"
    assert rows[0].quantity == 2  # summed by design
    assert rows[0].source == "meal"
    db.close()


def test_import_checked_then_reimport_creates_fresh_row():
    db = _db()
    db.add(models.Preferences(user_id=LOCAL_USER.id, pantry_staples=[]))
    meal = _make_meal(
        db, "Soup", [{"name": "leek", "quantity": 2, "unit": "piece", "in_stock": False}]
    )
    shopping.import_meal(meal.id, user=LOCAL_USER, db=db)
    row = db.query(models.ShoppingListItem).one()
    row.checked = True
    db.commit()

    shopping.import_meal(meal.id, user=LOCAL_USER, db=db)
    rows = db.query(models.ShoppingListItem).order_by(models.ShoppingListItem.id).all()
    assert len(rows) == 2  # checked rows are already in the cart; new open row created
    assert rows[0].checked and not rows[1].checked
    db.close()
