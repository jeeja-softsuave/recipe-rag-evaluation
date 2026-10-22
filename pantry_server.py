"""The capstone MCP server: recipe search, allergen declarations, scaling, substitution and
safe temperatures over the capstone corpus. Runs over stdio for the agent, and for any other
MCP client (Thursday's reviewer uses their own).

No model call happens here. Every tool reads the caller's trace id from the MCP request's
_meta and writes one server-side span to logs/capstone_spans.jsonl, so a single trace id
survives the MCP hop.

Allergen answers come from the declaration FIELDS (allergens, may_contain) by exact match,
never from the prose of the allergen note.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

import chromadb
from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

import tools
from capstone_corpus import (
    COLLECTION,
    current_version,
    load_cards,
    safety_chart,
    version_key,
    versions_of,
)
from recipe_rag import CHROMA_DIR, search_hybrid_rrf
from recipe_server import substitute_ingredient as week9_substitute
from telemetry import extract_context, setup as setup_telemetry

SPAN_LOG = Path(__file__).parent / "logs" / "capstone_spans.jsonl"
SEARCH_TOP_K = 5
ALLERGEN_VOCABULARY = list(tools.AVOIDABLE)
INGREDIENT_ROW = tools.INGREDIENT_ROW_PATTERN

server = MCPServer("pantry")
TRACER = setup_telemetry("pantry-server")
Allergen = Literal[tuple(ALLERGEN_VOCABULARY)]  # type: ignore[valid-type]
RecipeId = Literal[tuple(sorted({card["recipe_id"] for card in load_cards().values()}))]  # type: ignore[valid-type]
Version = Literal["current", "original", "reformulated-2025"]


def _span(ctx: Context | None, tool: str, started: float, detail: dict[str, Any]) -> None:
    """Write one server-side span, tagged with the caller's trace id if it sent one."""
    meta = getattr(ctx.request_context, "meta", None) if ctx else None
    meta = meta if isinstance(meta, dict) else {}
    trace_id = meta.get("trace_id")
    elapsed_ns = int((time.perf_counter() - started) * 1e9)
    # OpenTelemetry: a child of the caller's span, via the W3C traceparent it sent in _meta.
    span = TRACER.start_span(f"mcp.server {tool}", context=extract_context(meta),
                             start_time=time.time_ns() - elapsed_ns)
    span.set_attributes({"pantry.trace_id": str(trace_id), "mcp.tool": tool,
                         **{f"pantry.{k}": json.dumps(v) if isinstance(v, (list, dict)) else str(v)
                            for k, v in detail.items()}})
    span.end()
    SPAN_LOG.parent.mkdir(exist_ok=True)
    with SPAN_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "trace_id": trace_id, "process": "pantry-server", "span": f"mcp:{tool}",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "cost_usd": 0.0, **detail}) + "\n")


def _card(recipe_id: str, version: str) -> dict[str, Any] | None:
    """One version of a recipe; 'current' means whichever the CMS marks current."""
    if version == "current":
        return current_version(recipe_id)
    return load_cards().get(version_key(recipe_id, version))


@server.tool()
def search_recipes(
    query: Annotated[str, Field(description="What the user is asking about, in their words.")],
    ctx: Context,
) -> dict[str, Any]:
    """Search the recipe library and return the best-matching passages, each with the recipe
    id, its VERSION (original or reformulated-2025) and STATUS (current or superseded).
    Cite passages by their chunk_id; the chunk_id names the version. Some recipes exist in two
    versions; a superseded version is no longer what the publisher serves. Search only: does
    not check allergens, scale quantities or suggest substitutes."""
    started = time.perf_counter()
    collection = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)
    hits = search_hybrid_rrf(collection, query, SEARCH_TOP_K)
    cards = load_cards()
    passages = []
    for hit in hits:
        key = hit["chunk_id"].split("::")[0]
        card = cards[key]
        passages.append({"chunk_id": hit["chunk_id"], "recipe_id": card["recipe_id"],
                         "version": card["version"], "status": card["status"],
                         "section": hit["section"], "text": hit["text"]})
    _span(ctx, "search_recipes", started, {"chunk_ids": [p["chunk_id"] for p in passages]})
    return {"passages": passages}


@server.tool()
def check_allergens(
    recipe_id: Annotated[RecipeId, Field(description="The recipe to check.")],
    avoid: Annotated[list[Allergen], Field(description="Every allergen the user must avoid.")],
    ctx: Context,
    version: Annotated[Version, Field(description="Which version; leave as 'current' unless "
                                                  "the user asks about an older one.")] = "current",
) -> dict[str, Any]:
    """Check a recipe against the user's allergens using the recipe's DECLARATION FIELDS
    (declared allergens and 'may contain' traces), by exact match. This is the only reliable
    source for allergen safety; do not judge safety from recipe prose. Returns, per allergen,
    'contains', 'may_contain' or 'not_declared', the version checked, and an overall verdict:
    unsafe, may_contain or no_declared_allergen."""
    started = time.perf_counter()
    card = _card(recipe_id, version)
    if card is None:
        return {"checked": False, "reason": f"{recipe_id} has no {version} version",
                "versions": [c["version"] for c in versions_of(recipe_id)]}
    per = {a: ("contains" if a in card["allergens"] else
               "may_contain" if a in card["may_contain"] else "not_declared") for a in avoid}
    verdict = ("unsafe" if "contains" in per.values() else
               "may_contain" if "may_contain" in per.values() else "no_declared_allergen")
    result = {"checked": True, "recipe_id": recipe_id, "version": card["version"],
              "status": card["status"], "citation": f"{card['key']}", "per_allergen": per,
              "verdict": verdict, "declared_allergens": card["allergens"],
              "declared_may_contain": card["may_contain"]}
    _span(ctx, "check_allergens", started, {"recipe": card["key"], "verdict": verdict,
                                            "allergen_categories": sorted(per)})
    return result


@server.tool()
def scale_recipe(
    recipe_id: Annotated[RecipeId, Field(description="The recipe to scale.")],
    target_yield: Annotated[int, Field(ge=1, le=tools.MAX_TARGET_SERVINGS,
                                       description="Requested yield, in the recipe's yield unit.")],
    ctx: Context,
) -> dict[str, Any]:
    """Scale the CURRENT version of a recipe to a target yield. Ingredient weights scale;
    soak, ferment, stand and cook TIMES DO NOT, and are returned unchanged. Arithmetic only."""
    started = time.perf_counter()
    card = current_version(recipe_id)
    factor = target_yield / card["yield_qty"]
    rows = [{"ingredient": name.strip(), "grams": round(float(grams) * factor, 1)}
            for name, grams in INGREDIENT_ROW.findall(card["body"])
            if name.strip().lower() not in {"ingredient", "---"}]
    result = {"recipe_id": recipe_id, "version": card["version"], "citation": card["key"],
              "base_yield": f"{card['yield_qty']} {card['yield_unit']}",
              "target_yield": f"{target_yield} {card['yield_unit']}", "factor": round(factor, 4),
              "ingredients": rows, "times_unchanged": card["times"],
              "note": "Times do not scale with quantity; use them exactly as listed."}
    _span(ctx, "scale_recipe", started, {"recipe": card["key"], "factor": result["factor"]})
    return result


@server.tool()
def substitute_ingredient(
    ingredient: Annotated[str, Field(description="The ingredient exactly as the recipe names it.")],
    avoid: Annotated[Allergen, Field(description="The single constraint the swap must satisfy.")],
    ctx: Context,
) -> dict[str, Any]:
    """Replace ONE ingredient to satisfy ONE dietary constraint, from the test kitchen's
    substitution table, and report the allergens the replacement contains. If the name does
    not match, the result says so and suggests the recorded names to retry with."""
    started = time.perf_counter()
    result = week9_substitute(ingredient, avoid)
    _span(ctx, "substitute_ingredient", started,
          {"substituted": result.get("substituted"), "allergen_categories": [avoid]})
    return result


@server.tool()
def safe_temperature(
    item: Annotated[str, Field(description="Food or stage, e.g. 'chicken', 'leftovers', 'moru'.")],
    ctx: Context,
) -> dict[str, Any]:
    """Look up the safe cooking, reheating, holding or cooling temperature for a food in the
    food-safety chart. Any answer about cooking, reheating or storing food must state this
    number; 'cooked through' or 'golden' is never enough."""
    started = time.perf_counter()
    wanted = item.strip().lower()
    for entry in safety_chart():
        names = [entry["item"], *entry["aliases"]]
        if any(wanted == name or name in wanted for name in names):
            _span(ctx, "safe_temperature", started, {"item": entry["item"]})
            return {"found": True, **{k: v for k, v in entry.items() if k != "aliases"},
                    "source": "data/capstone/food_safety.json"}
    _span(ctx, "safe_temperature", started, {"item": None})
    return {"found": False, "item": item,
            "reason": "not in the food-safety chart; do not guess a temperature",
            "chart_items": [entry["item"] for entry in safety_chart()]}


if __name__ == "__main__":
    server.run()
