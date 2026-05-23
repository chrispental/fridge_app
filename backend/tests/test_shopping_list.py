from app.services.shopping_list import annotate_recipe, build_shopping_list
from app.services.staples import DEFAULT_STAPLES, is_staple


class _FakeMeal:
    def __init__(self, ingredients):
        self.recipe_json = {"ingredients": ingredients}


class _FakeItem:
    def __init__(self, name):
        self.name = name


def _ing(name, quantity=None, unit="unknown"):
    return {"name": name, "quantity": quantity, "unit": unit}


def _find(items, name):
    return next((i for i in items if i["name"].lower() == name.lower()), None)


def test_staple_matcher():
    assert is_staple("Salt", DEFAULT_STAPLES)
    assert is_staple("kosher salt", ["salt"])  # staple is a whole word within
    assert is_staple("black pepper", ["pepper"])
    assert is_staple("hot sauce", DEFAULT_STAPLES)
    assert not is_staple("saltine crackers", ["pepper"])
    assert not is_staple("", DEFAULT_STAPLES)


def test_staple_matcher_no_substring_false_positives():
    # The reported bug: "pepper" must NOT swallow these real ingredients.
    assert not is_staple("jalapeno peppers", ["salt", "pepper", "hot sauce"])
    assert not is_staple("bell peppers", ["pepper"])
    assert not is_staple("salted butter", ["salt"])


def test_staples_in_plan_reach_shopping_list():
    # A pepper variant in every meal must still land on the list, not be dropped.
    meals = [
        _FakeMeal([_ing("jalapeno peppers", 3, "piece"), _ing("salt", 1, "tsp")]),
        _FakeMeal([_ing("jalapeno peppers", 2, "piece")]),
    ]
    out = build_shopping_list(meals, inventory=[], staples=["salt", "pepper"])
    jalapeno = _find(out["to_buy"], "jalapeno peppers")
    assert jalapeno is not None
    assert jalapeno["quantity"] == 5  # merged across both meals
    assert _find(out["to_buy"], "salt") is None  # real staple still excluded


def test_merge_same_unit_sums_quantity():
    meals = [
        _FakeMeal([_ing("rice", 1, "cup")]),
        _FakeMeal([_ing("rice", 2, "cup")]),
    ]
    out = build_shopping_list(meals, inventory=[], staples=[])
    rice = _find(out["to_buy"], "rice")
    assert rice is not None
    assert rice["quantity"] == 3
    assert rice["unit"] == "cup"


def test_different_units_kept_separate():
    meals = [_FakeMeal([_ing("milk", 1, "cup"), _ing("milk", 1, "pint")])]
    out = build_shopping_list(meals, inventory=[], staples=[])
    units = sorted(i["unit"] for i in out["to_buy"] if i["name"] == "milk")
    assert units == ["cup", "pint"]


def test_have_vs_buy_split():
    meals = [_FakeMeal([_ing("chicken breast", 1, "lb"), _ing("saffron", 1, "pinch")])]
    out = build_shopping_list(meals, inventory=[_FakeItem("chicken")], staples=[])
    # "chicken" inventory matches "chicken breast" by bidirectional substring.
    assert _find(out["have"], "chicken breast") is not None
    assert _find(out["to_buy"], "saffron") is not None
    assert _find(out["to_buy"], "chicken breast") is None


def test_staples_excluded_and_reported():
    meals = [_FakeMeal([_ing("salt", 1, "tsp"), _ing("flour", 2, "cup")])]
    out = build_shopping_list(meals, inventory=[], staples=["salt", "pepper"])
    assert _find(out["to_buy"], "salt") is None
    assert _find(out["have"], "salt") is None
    assert out["staples_assumed"] == ["salt", "pepper"]
    assert _find(out["to_buy"], "flour") is not None


def test_annotate_recipe_applies_staples_live():
    # Stored state from when olive oil was NOT yet a staple.
    recipe = {
        "ingredients": [
            {"name": "olive oil", "quantity": 2, "unit": "tbsp", "in_stock": False},
            {"name": "chicken", "quantity": 1, "unit": "lb", "in_stock": False},
        ],
        "missing_ingredients": ["olive oil", "chicken"],
    }
    out = annotate_recipe(recipe, inventory=[_FakeItem("chicken")], staples=["olive oil"])
    by_name = {i["name"]: i for i in out["ingredients"]}
    assert by_name["olive oil"]["in_stock"] is True  # now a staple
    assert by_name["chicken"]["in_stock"] is True     # now in inventory
    assert out["missing_ingredients"] == []           # both removed from the buy note


def test_live_recompute_ignores_stored_in_stock():
    # Ingredient is flagged in_stock=False in the stored recipe, but it IS in
    # inventory now — it must land in "have", not "to_buy".
    meals = [_FakeMeal([{"name": "eggs", "quantity": 6, "unit": "piece", "in_stock": False}])]
    out = build_shopping_list(meals, inventory=[_FakeItem("eggs")], staples=[])
    assert _find(out["have"], "eggs") is not None
    assert _find(out["to_buy"], "eggs") is None
