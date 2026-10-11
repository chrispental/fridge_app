"""Import a recipe from a URL or pasted text into the app's recipe shape.

Deterministic first: recipe pages almost always carry schema.org `Recipe` JSON-LD,
which is parsed without any AI call. Pages without it, and pasted text, go through
the meal model with `prompts/import_system.md`. The result is a `MealSuggestion`
whose `source` points back at the page; the caller persists it as a saved meal.
"""
import ipaddress
import json
import logging
import re
import socket
from fractions import Fraction
from html import unescape
from urllib.parse import urlsplit

import httpx

from ..config import settings
from ..schemas import MealSuggestion, RecipeIngredient, RecipeSource
from .ai_client import call_structured
from .nutrition import parse_nutrition
from .prompts import load_prompt
from .units import normalize_unit

logger = logging.getLogger(__name__)

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 12_000
# Recipe sites commonly refuse requests that don't look like a browser; this is a
# user-initiated fetch of a public page, identified with the app token at the end.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36 FridgeChef/1.0"
)

_LD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S | re.I)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_DROP_RE = re.compile(r"<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")
_DURATION_RE = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", re.I)

_VULGAR = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}
_QTY_RE = re.compile(r"^\s*(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)(?:\s*(?:-|–|to)\s*(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?))?\s*(.*)$")
_PREP_RE = re.compile(r"\s*[,;(].*$")


class ImportError_(ValueError):
    """The input could not be turned into a recipe (bad URL, blocked host, nothing found)."""


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #
def _check_public_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ImportError_("Enter a full web address starting with http:// or https://.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ImportError_("That website could not be found.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        # The backend may sit next to private services; never let an import reach them.
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ImportError_("That address is not a public website.")
    return parts.geturl()


def fetch_page(url: str) -> str:
    """Download a public recipe page (bounded size); raises RuntimeError on network errors."""
    url = _check_public_url(url)
    try:
        with httpx.Client(timeout=settings.brave_request_timeout, follow_redirects=True,
                          headers={"User-Agent": _USER_AGENT, "Accept": "text/html,*/*;q=0.8",
                                   "Accept-Language": "en-US,en;q=0.9"}) as client:
            with client.stream("GET", url) as resp:
                if resp.status_code in (401, 403, 429):
                    raise RuntimeError("That site refused the request. Copy the recipe and paste it instead.")
                if resp.status_code >= 400:
                    raise RuntimeError(f"The page returned HTTP {resp.status_code}.")
                chunks, size = [], 0
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > MAX_PAGE_BYTES:
                        break
                    chunks.append(chunk)
                encoding = resp.encoding or "utf-8"
        return b"".join(chunks).decode(encoding, errors="replace")
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Could not fetch that page: {exc.__class__.__name__}.")


# --------------------------------------------------------------------------- #
# schema.org Recipe (JSON-LD)
# --------------------------------------------------------------------------- #
def _is_recipe(node) -> bool:
    if not isinstance(node, dict):
        return False
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.lower() == "recipe" for x in types)


def _walk(node):
    if isinstance(node, dict):
        if _is_recipe(node):
            yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _walk(node[key])
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def find_recipe_json_ld(html: str) -> dict | None:
    for block in _LD_RE.findall(html or ""):
        try:
            data = json.loads(unescape(block).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        for recipe in _walk(data):
            return recipe
    return None


def _text(value) -> str:
    if isinstance(value, dict):
        return _text(value.get("text") or value.get("name") or "")
    if isinstance(value, list):
        return " ".join(_text(v) for v in value)
    return unescape(_TAG_RE.sub("", str(value or ""))).strip()


def _steps(instructions) -> list[str]:
    out: list[str] = []
    if isinstance(instructions, str):
        parts = [p.strip() for p in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z])", unescape(_TAG_RE.sub("\n", instructions))) if p.strip()]
        return parts
    if isinstance(instructions, dict):
        instructions = [instructions]
    for item in instructions or []:
        if isinstance(item, dict) and str(item.get("@type", "")).lower() == "howtosection":
            out.extend(_steps(item.get("itemListElement")))
        else:
            text = _text(item)
            if text:
                out.append(text)
    return out


def _duration_minutes(value) -> int | None:
    if not isinstance(value, str):
        return None
    m = _DURATION_RE.match(value.strip())
    if not m:
        return None
    days, hours, minutes, seconds = (int(x) if x else 0 for x in m.groups())
    total = days * 1440 + hours * 60 + minutes + (1 if seconds else 0)
    return total or None


def _servings(value) -> int | None:
    for candidate in (value if isinstance(value, list) else [value]):
        m = re.search(r"\d+", str(candidate or ""))
        if m and 1 <= int(m.group()) <= 20:
            return int(m.group())
    return None


def _number(token: str) -> float:
    return float(sum(Fraction(part) for part in token.split()))


def parse_ingredient_line(line: str) -> RecipeIngredient:
    """'1 1/2 cups flour, sifted' -> flour, 1.5 cup. Unknown units stay unknown."""
    text = unescape(_TAG_RE.sub("", str(line or ""))).strip()
    for sym, frac in _VULGAR.items():
        text = text.replace(sym, f" {frac} ").replace("  ", " ")
    text = re.sub(r"(\d)\s+(\d/\d)", r"\1 \2", text).strip()
    quantity, unit, rest = None, "unknown", text
    m = _QTY_RE.match(text)
    if m:
        try:
            quantity = _number(m.group(1))
            rest = m.group(2)
        except (ValueError, ZeroDivisionError):
            quantity = None
    rest = re.sub(r"^\(.*?\)\s*", "", rest).strip()
    words = rest.split()
    if quantity is not None and words:
        first = words[0].rstrip(".").lower()
        two = " ".join(w.rstrip(".").lower() for w in words[:2])
        if normalize_unit(two) != "unknown" and len(words) > 2:
            unit, rest = normalize_unit(two), " ".join(words[2:])
        elif normalize_unit(first) != "unknown" and len(words) > 1:
            unit, rest = normalize_unit(first), " ".join(words[1:])
        elif first in ("g", "gram", "grams", "kg", "ml", "l", "liter", "litre", "litres", "liters", "cl") and len(words) > 1:
            unit, rest = "unknown", " ".join(words[1:])
            quantity = None  # a metric amount is not relabelled; the user checks it
        else:
            unit = "piece"
    name = _PREP_RE.sub("", rest).strip().lower()
    name = re.sub(r"^(of|fresh|large|small|medium)\s+", "", name).strip() or text.lower()
    return RecipeIngredient(name=name[:200], quantity=quantity, unit=unit, in_stock=False)


def recipe_from_json_ld(data: dict, url: str | None = None) -> MealSuggestion:
    title = _text(data.get("name")) or "Imported recipe"
    cuisine = _text(data.get("recipeCuisine")) or None
    method = (_text(data.get("cookingMethod")) or "stovetop").lower()
    ingredients = [parse_ingredient_line(line) for line in (data.get("recipeIngredient") or []) if _text(line)]
    total = _duration_minutes(data.get("totalTime"))
    if total is None:
        parts = [_duration_minutes(data.get(k)) for k in ("prepTime", "cookTime")]
        total = sum(p for p in parts if p) or None
    return MealSuggestion(
        title=title[:200],
        cuisine=cuisine,
        complexity=3,
        estimated_time_minutes=total,
        servings=_servings(data.get("recipeYield")),
        cooking_method=method,
        ingredients=ingredients,
        steps=_steps(data.get("recipeInstructions")),
        missing_ingredients=[],
        source=RecipeSource(title=title, url=url) if url else None,
        nutrition=parse_nutrition(data.get("nutrition"), source="recipe"),
    )


# --------------------------------------------------------------------------- #
# AI fallback
# --------------------------------------------------------------------------- #
def html_to_text(html: str) -> str:
    body = _DROP_RE.sub(" ", html or "")
    body = re.sub(r"</(p|div|li|h\d|tr|br)>", "\n", body, flags=re.I)
    text = unescape(_TAG_RE.sub(" ", body))
    text = _NL_RE.sub("\n\n", "\n".join(_WS_RE.sub(" ", line).strip() for line in text.splitlines()))
    return text.strip()[:MAX_TEXT_CHARS]


def recipe_from_text(text: str, url: str | None = None, title: str | None = None) -> MealSuggestion:
    from .meal_engine import SUGGESTION_SCHEMA, _parse_suggestions

    raw = call_structured(
        model=settings.openrouter_meal_model,
        system_prompt=load_prompt("import_system.md"),
        user_content=f"RECIPE TEXT\n{text.strip()[:MAX_TEXT_CHARS]}\n\nTranscribe the main recipe.",
        json_schema=SUGGESTION_SCHEMA,
        schema_name="recipe_import",
        temperature=0.1,
    )
    suggestions = _parse_suggestions(raw)
    if not suggestions:
        raise ImportError_("No recipe was found in that text.")
    recipe = suggestions[0]
    recipe.missing_ingredients = []
    for ing in recipe.ingredients:
        ing.in_stock = False
    if url:
        recipe.source = RecipeSource(title=title or recipe.title, url=url)
    return recipe


def import_recipe(*, url: str | None = None, text: str | None = None) -> MealSuggestion:
    """URL: schema.org JSON-LD when present, else AI over the page text. Text: AI."""
    if url and url.strip():
        html = fetch_page(url.strip())
        data = find_recipe_json_ld(html)
        if data is not None:
            recipe = recipe_from_json_ld(data, url.strip())
            if recipe.ingredients and recipe.steps:
                return recipe
        page_title = _text((_TITLE_RE.search(html) or [None, ""])[1]) or None
        body = html_to_text(html)
        if len(body) < 80:
            raise ImportError_("That page doesn't seem to contain a recipe.")
        return recipe_from_text(body, url.strip(), page_title)
    if text and text.strip():
        if len(text.strip()) < 20:
            raise ImportError_("Paste the whole recipe, including ingredients and steps.")
        return recipe_from_text(text)
    raise ImportError_("Paste a recipe or enter a web address.")
