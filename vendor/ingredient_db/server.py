"""Ingredient database MCP server - the content team's server (stand-in).

STAND-IN: written in-house for the Week 9 exercise because no real content-team server
exists. It is kept deliberately separate from the recipe app: its own directory, its own
data file, no imports from the app. It is assessed in risk_note.md as if a third party
had written it.

Tools: allergen lookup and per-100g nutrition lookup, both by ingredient name.
Resource: the full allergen matrix, for a host to attach as standing context.
Logs every lookup to queries.log next to this file (timestamp, tool, raw query).
No model call happens anywhere in this server.
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

HERE = Path(__file__).parent
DATA = json.loads((HERE / "ingredients.json").read_text(encoding="utf-8"))
QUERY_LOG = HERE / "queries.log"
SUGGESTION_LIMIT = 3
SUGGESTION_CUTOFF = 0.5

FLAGS: list[str] = DATA["flags"]
BY_NAME: dict[str, dict[str, Any]] = {}
for _row in DATA["ingredients"]:
    for _key in [_row["name"], *_row["aliases"]]:
        BY_NAME[_key.lower()] = _row

server = MCPServer("ingredient-db")

IngredientName = Annotated[
    str, Field(description="Ingredient name, e.g. 'urad dal' or 'Thick sour curd'.")
]


def _log(tool: str, query: str) -> None:
    """Append one lookup to the query log."""
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with QUERY_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp}\t{tool}\t{query}\n")


def _find(query: str) -> dict[str, Any] | None:
    """Exact name or alias match, case-insensitive; then a unique substring match."""
    wanted = " ".join(query.lower().split())
    if wanted in BY_NAME:
        return BY_NAME[wanted]
    partial = {id(row): row for key, row in BY_NAME.items() if wanted and wanted in key}
    return next(iter(partial.values())) if len(partial) == 1 else None


def _no_match(query: str) -> dict[str, Any]:
    """Unknown ingredient: say so, and offer the closest names so the caller can retry."""
    names = sorted({row["name"] for row in BY_NAME.values()})
    close = difflib.get_close_matches(query, names, n=SUGGESTION_LIMIT, cutoff=SUGGESTION_CUTOFF)
    return {
        "matched": False,
        "query": query,
        "reason": "ingredient not in the database",
        "did_you_mean": close,
    }


@server.tool()
def lookup_allergens(ingredient: IngredientName) -> dict[str, Any]:
    """Look up which allergen flags one ingredient carries."""
    _log("lookup_allergens", ingredient)
    row = _find(ingredient)
    if row is None:
        return _no_match(ingredient)
    return {
        "matched": True,
        "ingredient": row["name"],
        "allergens": {flag: flag in row["contains"] for flag in FLAGS},
    }


@server.tool()
def lookup_nutrition(ingredient: IngredientName) -> dict[str, Any]:
    """Look up per-100g nutrition (energy, protein, fat, carbohydrate, fibre, sodium) for one
    ingredient, by raw weight."""
    _log("lookup_nutrition", ingredient)
    row = _find(ingredient)
    if row is None:
        return _no_match(ingredient)
    return {"matched": True, "ingredient": row["name"], "per_100g": row["per_100g"]}


@server.resource(
    "ingredient-db://allergen-matrix",
    description="Every ingredient in the database against every allergen flag.",
)
def allergen_matrix() -> str:
    """The standing matrix: one line per ingredient, listing the flags it carries."""
    lines = [f"Allergen flags: {', '.join(FLAGS)}. Ingredients and the flags they carry:"]
    for row in DATA["ingredients"]:
        lines.append(f"- {row['name']}: {', '.join(row['contains']) or 'none'}")
    return "\n".join(lines)


if __name__ == "__main__":
    server.run()
