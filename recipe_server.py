"""Server one: the recipe-search MCP server (Week 9).

Exposes the three deterministic Week 7 tools from tools.py over MCP, plus the cards'
allergen notes as a resource. There is no model call anywhere in this process: the
server exposes capabilities, and the host (mcp_agent.py) runs the model.

The SDK publishes each function's docstring as the tool description the model reads,
so every docstring below is written for the model, not for a Python reader.

Run over stdio by an MCP host; stdout carries JSON-RPC, so nothing here may print.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

import tools

ALLERGEN_SECTION = "allergen_note"

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
    ingredient: Annotated[str, Field(description="The ingredient to replace.")],
    avoid: Annotated[Avoidable, Field(description="The dietary constraint.")],
) -> dict[str, Any]:
    """Replace one ingredient to satisfy one dietary constraint."""
    return tools.substitute_ingredient(ingredient, avoid)


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
