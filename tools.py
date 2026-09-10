"""The three tools, as plain Python. No model calls here.

Keeping every tool deterministic is what makes the Week 7 race meaningful: the only
difference between the agent and the workflow is who decides the order of calls, not
what the calls do.

Tool descriptions follow one rule: name exactly one job, then disclaim the jobs the
other two tools own. Overlapping descriptions are the documented cause of tool thrash,
and bolting "use the correct tool" onto the system prompt hides the bug instead of
fixing it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import chromadb

from recipe_rag import CHROMA_DIR, STRUCTURE_AWARE_COLLECTION, load_recipe_cards, search

SUBSTITUTIONS_FILE = Path(__file__).parent / "substitutions.json"

# Yields read off the card titles: "two dozen", "thirty idlis", "sixteen steamed cakes",
# "twelve appams", "1.6 litres" (eight 200ml glasses), "four servings".
BASE_YIELDS = {
    "kuzhi-paniyaram-batter-01": 24,
    "kallappam-batter-02": 12,
    "sanna-03": 16,
    "moru-04": 8,
    "idli-batter-05": 30,
    "neeragaram-06": 4,
}

RECIPE_IDS = sorted(BASE_YIELDS)
# Constraint vocabulary. Kept as an enum so the model cannot invent a constraint the
# substitution table has never heard of.
AVOIDABLE = ["dairy", "coconut", "nuts", "gluten", "alcohol", "yeast", "soy"]

INGREDIENT_ROW_PATTERN = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([\d.]+)\s*g\s*\|", re.MULTILINE)
MAX_TARGET_SERVINGS = 200


def _cards_by_id() -> dict[str, dict[str, Any]]:
    """Index the recipe cards by recipe_id."""
    return {card["recipe_id"]: card for card in load_recipe_cards()}


CARDS = _cards_by_id()


def _load_substitutions() -> list[dict[str, Any]]:
    """Load the substitution table this tool answers from."""
    return json.loads(SUBSTITUTIONS_FILE.read_text(encoding="utf-8"))["substitutions"]


SUBSTITUTIONS = _load_substitutions()


def _ingredient_rows(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull (ingredient, grams) out of a card's markdown ingredient tables."""
    rows = []
    for name, grams in INGREDIENT_ROW_PATTERN.findall(card["body"]):
        if name.lower() in {"ingredient", "---"}:
            continue
        rows.append({"ingredient": name.strip(), "grams": float(grams)})
    return rows


def search_recipes(dish: str) -> dict[str, Any]:
    """Find one recipe card by dish name."""
    collection = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(
        STRUCTURE_AWARE_COLLECTION
    )
    hits = search(collection, dish, top_k=3)
    if not hits:
        return {"found": False, "reason": "no recipe card matches that dish"}
    recipe_id = hits[0]["recipe_id"]
    card = CARDS.get(recipe_id)
    if card is None:
        return {"found": False, "reason": f"retrieved unknown recipe_id {recipe_id}"}
    return {
        "found": True,
        "recipe_id": recipe_id,
        "title": card["title"],
        "base_yield": BASE_YIELDS[recipe_id],
        "dietary_tags": card["dietary_tags"],
        "ingredients": _ingredient_rows(card),
    }


def scale_recipe(recipe_id: str, target_servings: int) -> dict[str, Any]:
    """Multiply one recipe's ingredient weights to a target yield."""
    if recipe_id not in BASE_YIELDS:
        return {"scaled": False, "reason": f"unknown recipe_id {recipe_id}"}
    if not isinstance(target_servings, int) or target_servings < 1:
        return {"scaled": False, "reason": "target_servings must be a positive integer"}
    if target_servings > MAX_TARGET_SERVINGS:
        return {"scaled": False, "reason": f"target_servings above {MAX_TARGET_SERVINGS}"}
    base = BASE_YIELDS[recipe_id]
    factor = target_servings / base
    rows = [
        {"ingredient": row["ingredient"], "grams": round(row["grams"] * factor, 1)}
        for row in _ingredient_rows(CARDS[recipe_id])
    ]
    return {
        "scaled": True,
        "recipe_id": recipe_id,
        "base_yield": base,
        "target_servings": target_servings,
        "factor": round(factor, 4),
        "ingredients": rows,
    }


def substitute_ingredient(ingredient: str, avoid: str) -> dict[str, Any]:
    """Replace one ingredient to satisfy one dietary constraint."""
    if avoid not in AVOIDABLE:
        return {"substituted": False, "reason": f"avoid must be one of {AVOIDABLE}"}
    wanted = ingredient.strip().lower()
    for entry in SUBSTITUTIONS:
        if entry["ingredient"].lower() != wanted or entry["avoid"] != avoid:
            continue
        return {
            "substituted": True,
            "ingredient": entry["ingredient"],
            "avoid": avoid,
            "substitute": entry["substitute"],
            # The replacement's own allergens. This is what makes a cascade possible:
            # a substitute can itself violate another constraint in the same request.
            "substitute_contains": entry["contains"],
            "source": entry["source"],
        }
    return {
        "substituted": False,
        "ingredient": ingredient,
        "avoid": avoid,
        "reason": "no substitution recorded for that ingredient and constraint",
    }


# The tool schemas handed to the model. Descriptions are deliberately non-overlapping:
# each says what it does, then what it does NOT do.
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_recipes",
        "description": (
            "Find one recipe card by dish name and return its recipe_id, base yield, "
            "dietary tags and ingredient weights in grams. Search only. Does not scale "
            "quantities and does not substitute or check ingredients for allergens."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dish": {
                    "type": "string",
                    "description": "Dish name as the user said it, e.g. 'idli batter'.",
                }
            },
            "required": ["dish"],
        },
    },
    {
        "type": "function",
        "name": "scale_recipe",
        "description": (
            "Multiply the ingredient weights of one already-identified recipe to a target "
            "yield. Arithmetic only. Requires a recipe_id obtained from search_recipes. "
            "Does not find recipes and does not substitute or check ingredients."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "recipe_id": {
                    "type": "string",
                    "enum": RECIPE_IDS,
                    "description": "recipe_id returned by search_recipes.",
                },
                "target_servings": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_TARGET_SERVINGS,
                    "description": "Requested yield in the same unit as base_yield.",
                },
            },
            "required": ["recipe_id", "target_servings"],
        },
    },
    {
        "type": "function",
        "name": "substitute_ingredient",
        "description": (
            "Replace exactly one ingredient to satisfy exactly one dietary constraint, and "
            "report which allergens the replacement itself contains. One ingredient and one "
            "constraint per call; call it again if the replacement violates another "
            "constraint. Does not find recipes and does not scale quantities."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ingredient": {
                    "type": "string",
                    "description": "The single ingredient to replace, as named on the card.",
                },
                "avoid": {
                    "type": "string",
                    "enum": AVOIDABLE,
                    "description": "The single dietary constraint the replacement must satisfy.",
                },
            },
            "required": ["ingredient", "avoid"],
        },
    },
]

TOOLS = {
    "search_recipes": search_recipes,
    "scale_recipe": scale_recipe,
    "substitute_ingredient": substitute_ingredient,
}


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one tool call, returning an error dict rather than raising."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool {name}"}
    try:
        return tool(**arguments)
    except TypeError as error:
        return {"error": f"bad arguments for {name}: {error}"}
