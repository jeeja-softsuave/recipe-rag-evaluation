"""Server one: the recipe-search MCP server (Week 9).

Exposes the three deterministic Week 7 tools from tools.py over MCP, plus the cards'
allergen notes as a resource. There is no model call anywhere in this process: the
server exposes capabilities, and the host (mcp_agent.py) runs the model.

The SDK publishes each function's docstring as the tool description the model reads,
so every docstring below is written for the model, not for a Python reader.

Run over stdio by an MCP host; stdout carries JSON-RPC, so nothing here may print.
"""

from __future__ import annotations

import difflib
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

import tools

ALLERGEN_SECTION = "allergen_note"
SUGGESTION_LIMIT = 3
SUGGESTION_CUTOFF = 0.6

server = MCPServer("recipe-search")

RecipeId = Literal[tuple(tools.RECIPE_IDS)]  # type: ignore[valid-type]
Avoidable = Literal[tuple(tools.AVOIDABLE)]  # type: ignore[valid-type]


@server.tool()
def search_recipes(
    dish: Annotated[str, Field(description="Dish name as the user said it, e.g. 'idli batter'.")],
) -> dict[str, Any]:
    """Find one recipe card by dish name and return its recipe_id, base yield, dietary tags
    and ingredient weights in grams. Search only. Does not scale quantities and does not
    substitute or check ingredients for allergens."""
    return tools.search_recipes(dish)


@server.tool()
def scale_recipe(
    recipe_id: Annotated[RecipeId, Field(description="recipe_id returned by search_recipes.")],
    target_servings: Annotated[
        int,
        Field(ge=1, le=tools.MAX_TARGET_SERVINGS,
              description="Requested yield in the same unit as base_yield."),
    ],
) -> dict[str, Any]:
    """Multiply the ingredient weights of one already-identified recipe to a target yield.
    Arithmetic only. Requires a recipe_id obtained from search_recipes. Does not find
    recipes and does not substitute or check ingredients."""
    return tools.scale_recipe(recipe_id, target_servings)


@server.tool()
def substitute_ingredient(
    ingredient: Annotated[
        str,
        Field(description="The ingredient exactly as the recipe card or an earlier substitute "
                          "result names it, e.g. 'Thick sour curd', not 'curd'."),
    ],
    avoid: Annotated[
        Avoidable, Field(description="The single dietary constraint the replacement must satisfy.")
    ],
) -> dict[str, Any]:
    """Replace exactly ONE ingredient to satisfy exactly ONE dietary constraint, from the app's
    recorded substitution table, and report which allergens the replacement itself contains.

    Use it when the user must avoid dairy, coconut, nuts, gluten, alcohol, yeast or soy and a
    recipe ingredient contains it. Name the ingredient exactly as the card names it; a short or
    everyday name will not match.

    Reading the result:
    - substituted true: read substitute_contains. If the replacement contains something else
      the user avoids, call this tool again on the replacement.
    - substituted false, recoverable true: the name did not match. Retry with a name from
      did_you_mean.
    - substituted false, recoverable false: no substitute is recorded. Tell the user that, and
      do not suggest substitutes of your own: an unrecorded swap has unchecked allergens.

    Does not find recipes and does not scale quantities."""
    result = tools.substitute_ingredient(ingredient, avoid)
    # An unknown avoid value never gets here: the schema's enum rejects it first.
    if result.get("substituted"):
        return result
    return {**result, **_explain_miss(ingredient, avoid)}


def _explain_miss(ingredient: str, avoid: str) -> dict[str, Any]:
    """Tell a spelling miss apart from a genuine dead end, and say how to recover."""
    wanted = " ".join(ingredient.lower().split())
    names = sorted({entry["ingredient"] for entry in tools.SUBSTITUTIONS})
    if wanted in {name.lower() for name in names}:
        constraints = sorted(
            entry["avoid"] for entry in tools.SUBSTITUTIONS if entry["ingredient"].lower() == wanted
        )
        return {
            "recoverable": False,
            "reason": f"'{ingredient}' is in the substitution table, but no substitute is "
                      f"recorded for avoid={avoid} (recorded only for: {', '.join(constraints)}). "
                      f"No safe substitute exists in the data; do not invent one.",
        }
    for_this_constraint = [e["ingredient"] for e in tools.SUBSTITUTIONS if e["avoid"] == avoid]
    containing = [name for name in names if wanted and wanted in name.lower()]
    close = difflib.get_close_matches(ingredient, names, n=SUGGESTION_LIMIT, cutoff=SUGGESTION_CUTOFF)
    suggestions = list(dict.fromkeys(containing + close))
    suggestions.sort(key=lambda name: name not in for_this_constraint)
    if suggestions:
        hint = f"try '{suggestions[0]}'"
    else:
        hint = f"recorded ingredients for avoid={avoid}: {for_this_constraint}"
    return {
        "recoverable": True,
        "did_you_mean": suggestions[:SUGGESTION_LIMIT],
        "reason": f"no ingredient named '{ingredient}' in the substitution table: {hint}",
    }


@server.resource(
    "recipe://allergen-notes",
    description="Standing allergen note for every recipe card, plus the constraint vocabulary.",
)
def allergen_notes() -> str:
    """App-attached context: the same on every turn, so it is not a tool."""
    lines = [f"Dietary constraints the tools understand: {', '.join(tools.AVOIDABLE)}."]
    for recipe_id, card in sorted(tools.CARDS.items()):
        note = " ".join(card["sections"].get(ALLERGEN_SECTION, "").split())
        lines.append(f"- {recipe_id} ({card['title']}): {note}")
    return "\n".join(lines)


if __name__ == "__main__":
    server.run()
