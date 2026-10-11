"""Store sections ("aisles") for shopping-list rows.

A shopping row gets a category when it is created (guessed from its name, or
chosen by the user) so the list can be walked aisle by aisle. The vocabulary is
the inventory category set, so a bought item carries its category into the fridge
where the storage guess and shelf-life estimate already understand it.
"""
import re

# Display order of the aisles, roughly a supermarket walk. Must match AISLES in
# frontend/src/utils/aisles.js.
AISLES: list[str] = [
    "produce", "bakery", "meat", "seafood", "dairy", "frozen",
    "pantry", "condiment", "beverage", "other",
]

# Whole-word keywords (singular; plurals are matched by the regex). Earlier
# entries win, so "coconut milk" is pantry before "milk" is dairy.
_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    # Fresh items whose names contain a pantry word ("pepper", "chili") come first.
    ("produce", ("bell pepper", "red pepper", "green pepper", "yellow pepper", "sweet pepper", "chili pepper",
                 "chilli", "jalapeno", "jalapeño", "serrano", "habanero", "poblano", "fresh ginger", "fresh herb")),
    ("pantry", ("coconut milk", "almond milk", "oat milk", "soy milk", "canned", "can of", "flour", "sugar", "rice", "pasta",
                "spaghetti", "noodle", "lentil", "chickpea", "bean", "oat", "cereal", "quinoa", "couscous", "stock",
                "broth", "bouillon", "tomato paste", "crushed tomato", "diced tomato", "tomato sauce", "coconut cream",
                "baking powder", "baking soda", "yeast", "cornstarch", "breadcrumb", "panko", "nut", "almond", "walnut",
                "peanut", "cashew", "pecan", "seed", "raisin", "dried", "honey", "syrup", "jam", "peanut butter",
                "tahini", "chocolate", "cocoa", "vanilla", "spice", "cumin", "paprika", "cinnamon", "oregano",
                "thyme", "turmeric", "curry powder", "chili powder", "chili flake", "bay leaf", "salt", "pepper",
                "oil", "olive oil", "sesame oil", "vegetable oil", "tortilla chip", "cracker", "pretzel", "popcorn")),
    ("condiment", ("sauce", "ketchup", "mustard", "mayo", "mayonnaise", "vinegar", "dressing", "salsa", "relish",
                   "pickle", "hot sauce", "sriracha", "soy sauce", "fish sauce", "oyster sauce", "hoisin", "miso",
                   "pesto", "hummus", "chutney", "wasabi", "horseradish", "worcestershire", "mirin", "cooking wine")),
    ("frozen", ("frozen", "ice cream", "popsicle", "sorbet")),
    ("seafood", ("shrimp", "prawn", "salmon", "tuna", "cod", "tilapia", "fish", "crab", "lobster", "scallop",
                 "clam", "mussel", "oyster", "squid", "calamari", "anchovy", "sardine", "halibut", "trout", "seafood")),
    ("meat", ("chicken", "beef", "pork", "turkey", "lamb", "bacon", "sausage", "ham", "steak", "mince", "ground",
              "veal", "duck", "chorizo", "salami", "pepperoni", "prosciutto", "meatball", "brisket", "rib", "thigh",
              "breast", "wing", "drumstick", "deli meat", "hot dog")),
    ("dairy", ("milk", "cheese", "cheddar", "mozzarella", "parmesan", "feta", "gruyere", "gruyère", "brie", "gouda",
               "butter", "yogurt", "yoghurt", "cream", "sour cream", "cream cheese", "egg", "ricotta", "cottage cheese",
               "half and half", "whipping cream", "ghee", "kefir", "tofu", "tempeh")),
    ("bakery", ("bread", "bun", "roll", "bagel", "tortilla", "pita", "naan", "baguette", "croissant", "muffin",
                "wrap", "flatbread", "sourdough", "brioche", "cake", "pastry")),
    ("beverage", ("juice", "soda", "cola", "sparkling water", "bottled water", "coffee", "tea", "wine", "beer",
                  "kombucha", "lemonade", "cider", "seltzer", "tonic", "milkshake", "energy drink")),
    ("produce", ("onion", "garlic", "lemon", "lime", "tomato", "potato", "sweet potato", "carrot", "celery", "lettuce",
                 "spinach", "kale", "cabbage", "broccoli", "cauliflower", "pepper", "bell pepper", "chili", "jalapeno",
                 "cucumber", "zucchini", "squash", "pumpkin", "mushroom", "avocado", "apple", "banana", "orange",
                 "berry", "strawberry", "blueberry", "raspberry", "grape", "melon", "watermelon", "pineapple", "mango",
                 "peach", "pear", "plum", "cherry", "kiwi", "ginger", "scallion", "green onion", "spring onion", "leek",
                 "shallot", "herb", "parsley", "cilantro", "coriander", "basil", "mint", "dill", "rosemary", "chive",
                 "corn", "pea", "green bean", "asparagus", "eggplant", "aubergine", "beet", "radish", "turnip",
                 "fennel", "artichoke", "bok choy", "choy sum", "bean sprout", "sprout", "salad", "arugula", "rocket",
                 "chard", "lemongrass", "edamame", "okra", "plantain", "fig", "date", "coconut", "pomegranate")),
]

_VALID = set(AISLES)


def _word_re(keyword: str) -> re.Pattern:
    return re.compile(r"(?<![a-z])" + re.escape(keyword) + r"(?:s|es)?(?![a-z])")


_COMPILED = [(aisle, [_word_re(k) for k in words]) for aisle, words in _KEYWORDS]


def normalize_category(value: str | None) -> str | None:
    v = (value or "").strip().lower()
    return v if v in _VALID else None


def guess_category(name: str) -> str:
    """Best-effort store section for an ingredient name; 'other' when nothing matches."""
    text = (name or "").lower()
    for aisle, patterns in _COMPILED:
        if any(p.search(text) for p in patterns):
            return aisle
    return "other"
