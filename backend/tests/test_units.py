from app.services.units import ALL_UNITS, normalize_unit, to_base, try_subtract


def test_normalize_known_units():
    assert normalize_unit("lb") == "lb"
    assert normalize_unit("Pounds") == "lb"
    assert normalize_unit("OZ") == "oz"
    assert normalize_unit("ounces") == "oz"
    assert normalize_unit("pieces") == "piece"
    assert normalize_unit("Cups") == "cup"
    assert normalize_unit("gal") == "gallon"
    assert normalize_unit("fl oz") == "fl oz"
    assert normalize_unit("fluid ounces") == "fl oz"


def test_normalize_unknown_units():
    assert normalize_unit("") == "unknown"
    assert normalize_unit(None) == "unknown"
    assert normalize_unit("blorp") == "unknown"
    # metric units are not in the US vocabulary and must not be mislabeled
    assert normalize_unit("g") == "unknown"
    assert normalize_unit("ml") == "unknown"


def test_all_units_present():
    assert "unknown" in ALL_UNITS
    assert "piece" in ALL_UNITS
    assert "lb" in ALL_UNITS


def test_to_base_conversion():
    assert to_base(2, "lb") == ("mass", 32.0)
    assert to_base(1, "gallon") == ("volume", 128.0)
    assert to_base(2, "cup") == ("volume", 16.0)
    assert to_base(5, "piece") == ("count", 5.0)
    assert to_base(1, "unknown") is None
    assert to_base(None, "lb") is None


def test_subtract_same_unit():
    assert try_subtract(16, "oz", 6, "oz") == 10


def test_subtract_cross_unit():
    # 2 lb = 32 oz; minus 8 oz leaves 24 oz = 1.5 lb
    assert try_subtract(2, "lb", 8, "oz") == 1.5
    # 1 gallon = 128 fl oz; minus 2 quart (64) leaves 64 fl oz = 0.5 gallon
    assert try_subtract(1, "gallon", 2, "quart") == 0.5


def test_subtract_incompatible_dimensions():
    assert try_subtract(1, "cup", 1, "piece") is None


def test_subtract_unknown_unit():
    assert try_subtract(1, "unknown", 1, "oz") is None


def test_subtract_never_negative():
    assert try_subtract(8, "oz", 20, "oz") == 0.0
