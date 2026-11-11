"""Instant answers: questions the kitchen tools can answer alone skip the model entirely.

The agent (pantry.answer) takes 2-4 model calls per question, and on the free tier each call
waits 10-40 s in Google's queue. But three kinds of question need no language model at all:

- an allergy yes/no about one library recipe  -> check_allergens (exact match on the declaration)
- scaling one recipe to a number of its units  -> scale_recipe (grams scale, times do not)
- a storage, reheating or cooking temperature  -> safe_temperature (the chart, as a number)

route() recognises those narrowly and returns None for everything else, which then goes to the
agent as before. Anything mixed, ambiguous, screened as an injection, or phrased as "make it
without ..." goes to the agent. The answer is written from the tool result by the same host
code the agent's answers pass through (declaration_first, the guards), so it carries the same
declaration header, verdict line and version-named citation. Validated offline against the 32
eval cases with the same 15 assertions (test_speed.py).
"""

from __future__ import annotations

import json
import re
import secrets
import time
from typing import Any

import pantry
import pantry_server
from capstone_corpus import load_cards, safety_chart, stated_allergens
from security import screen_input

# Words that name an allergen only for routing; stated_allergens() stays as the eval defines it.
EXTRA_ALLERGEN_WORDS = {r"coeliac|celiac|gluten[- ]free": "gluten", r"lactose|milk[- ]free": "dairy"}
# "make it without", "instead of", "swap", or several recipes: the agent reasons those through.
NEEDS_AGENT = re.compile(r"\b(?:instead|substitut\w*|swap\w*|replac\w*|without|alternative|what (?:can|could|should) i "
                         r"(?:make|use|cook)|which of|ingredients?|what goes into|recipe for|make\s+\w+\s+for)\b", re.I)
# An allergy question must be a yes/no about eating or serving the recipe.
YES_NO = re.compile(r"^\s*(?:can|could|is|are|was|were|does|do|would)\b|\b(?:safe|suitable|ok|okay|alright)\b|"
                    r"\bcan\s+(?:\w+\s+){0,3}(?:eat|have)\b|\b\w+[- ]free\?", re.I)
OLD_VERSION = re.compile(r"\b(?:original|old|older|previous|earlier)\b", re.I)
TEMPERATURE_WORDS = re.compile(r"\b(?:temperature|reheat\w*|store|storing|stored|keep|kept|cool\w*|chill\w*|"
                               r"refrigerat\w*|fridge|counter|room temp\w*|cook\w* .{0,30}\bdone|degrees|°c)\b", re.I)
UNIT_STEMS = {"paniyarams": "paniyaram", "appams": "appam", "steamed cakes": "cake", "200ml glasses": "glass",
              "idlis": "idli", "servings": "serving"}


def _current_cards() -> dict[str, dict[str, Any]]:
    return {c["recipe_id"]: c for c in load_cards().values() if c["status"] == "current"}


def _recipes_named(lowered: str) -> list[str]:
    return sorted({rid for word, rid in pantry.RECIPE_WORDS.items() if re.search(rf"\b{word}s?\b", lowered)})


def _allergens(question: str) -> list[str]:
    found = set(stated_allergens(question))
    for pattern, allergen in EXTRA_ALLERGEN_WORDS.items():
        if re.search(rf"\b(?:{pattern})\b", question, re.I):
            found.add(allergen)
    return sorted(found)


def _scale_target(lowered: str) -> tuple[str, int] | None:
    """'120 idlis', '48 kuzhi paniyarams', '8 cakes': the recipe is the one whose yield unit
    follows the number, so 'how much idli rice' in a paniyaram question does not confuse it."""
    hits = set()
    for recipe_id, card in _current_cards().items():
        stem = UNIT_STEMS.get(card["yield_unit"], card["yield_unit"].rstrip("s"))
        for number in re.findall(rf"\b(\d{{1,3}})\s+(?:[a-z]+\s+){{0,2}}?{re.escape(stem)}s?\b", lowered):
            hits.add((recipe_id, int(number)))
    return hits.pop() if len(hits) == 1 else None


def _chart_name(lowered: str) -> str | None:
    """The longest chart name or alias in the question ('leftover idlis' -> 'leftover idli')."""
    names = sorted({n for e in safety_chart() for n in [e["item"], *e["aliases"]]}, key=len, reverse=True)
    return next((n for n in names if re.search(rf"\b{re.escape(n)}s?\b", lowered)), None)


def route(question: str) -> dict[str, Any] | None:
    """The one tool that answers this question alone, with its arguments; None means the agent."""
    if (screen_input(question) or len(question) > 300 or NEEDS_AGENT.search(question)
            or question.count("?") > 1):  # two questions in one: the agent answers both
        return None
    lowered = question.lower()
    recipes, avoid = _recipes_named(lowered), _allergens(question)
    scale, chart = _scale_target(lowered), _chart_name(lowered)
    routes = []
    if avoid and len(recipes) == 1 and YES_NO.search(question) and not TEMPERATURE_WORDS.search(question) and not scale:
        routes.append({"tool": "check_allergens", "recipe_id": recipes[0], "avoid": avoid,
                       "version": "original" if OLD_VERSION.search(question) else "current"})
    if scale:
        routes.append({"tool": "scale_recipe", "recipe_id": scale[0], "target_yield": scale[1]})
    if chart and TEMPERATURE_WORDS.search(question) and not avoid:
        routes.append({"tool": "safe_temperature", "item": chart})
    return routes[0] if len(routes) == 1 else None  # mixed intent: let the agent handle it


def _allergen_body(result: dict[str, Any], title: str) -> str:
    cite = f"[{result['citation']}]"
    asked = ", ".join(result["per_allergen"])
    hits = ", ".join(a for a, v in result["per_allergen"].items() if v != "not_declared")
    if result["verdict"] == "unsafe":
        body = f"No. {title} {cite} declares {hits} as an ingredient, so it is not safe for someone avoiding {asked}."
    elif result["verdict"] == "may_contain":
        body = (f"Treat it as not safe. The declaration for {title} {cite} says it may contain {hits} "
                f"(cross-contact), so serve it to someone avoiding {hits} only with a supplier's guarantee.")
    else:
        body = (f"{title} {cite} declares no {asked}: the declaration lists it neither as an ingredient nor as "
                f"a may-contain. Still check the labels of the ingredients you buy.")
    if result["status"] != "current":
        current = pantry_server.check_allergens(result["recipe_id"], list(result["per_allergen"]), None)
        body += (f" Note: this is the superseded {result['version']} version; the recipe served today is "
                 f"{current['citation']}. Check that version before cooking.")
    return body


def _scale_body(result: dict[str, Any]) -> str:
    lines = [f"Scaling {result['base_yield']} to {result['target_yield']} (x{result['factor']:g}) "
             f"[{result['citation']}]:"]
    lines += [f"- {i['ingredient']}: {i['grams']:g} g" for i in result["ingredients"]]
    times = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in result["times_unchanged"].items())
    lines.append(f"Times do not scale with quantity; use them exactly as listed: {times}.")
    return "\n".join(lines)


def _temperature_body(result: dict[str, Any]) -> str:
    if not result.get("found"):
        return (f"{result['item']} is not in the food-safety chart, so I won't guess a temperature. "
                f"The chart covers: {', '.join(result['chart_items'])}.")
    value = result.get("min_internal_c", result.get("max_hold_c"))
    limit = "at least" if "min_internal_c" in result else "at or below"
    body = f"{result['item'].capitalize()}: {limit} {value} °C. {result['rule']}"
    if result.get("max_cool_hours"):
        body += f" (within {result['max_cool_hours']} hours)"
    return body + " (food-safety chart)"


def answer(question: str, log: bool = True) -> dict[str, Any] | None:
    """An instant answer in the agent's record shape, or None when the agent is needed."""
    plan = route(question)
    if plan is None:
        return None
    with pantry.TRACER.start_as_current_span("pantry.fast_answer") as span:
        trace_id, started = "t-" + secrets.token_hex(6), time.perf_counter()
        tool_started = time.perf_counter()
        if plan["tool"] == "check_allergens":
            arguments = {"recipe_id": plan["recipe_id"], "avoid": plan["avoid"], "version": plan["version"]}
            result = pantry_server.check_allergens(plan["recipe_id"], plan["avoid"], None, plan["version"])
            title = load_cards()[result["citation"]]["title"]
            body = _allergen_body(result, title)
        elif plan["tool"] == "scale_recipe":
            arguments = {"recipe_id": plan["recipe_id"], "target_yield": plan["target_yield"]}
            result = pantry_server.scale_recipe(plan["recipe_id"], plan["target_yield"], None)
            body = _scale_body(result)
        else:
            arguments = {"item": plan["item"]}
            result = pantry_server.safe_temperature(plan["item"], None)
            body = _temperature_body(result)
        calls = [{"lap": None, "server": "pantry", "tool": plan["tool"], "arguments": arguments,
                  "is_error": False, "result": json.dumps(result)}]
        spans = [{"span": f"tool:{plan['tool']} (instant)", "server": "pantry",
                  "latency_ms": round((time.perf_counter() - tool_started) * 1000, 1),
                  "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "is_error": False}]
        # The same host code the agent's answers pass through: declaration first, then the guards.
        final, verdict = pantry.declaration_first(body, calls)
        final, guard = pantry.swap_guard(question, final, calls)
        final, contradiction = pantry.withhold_contradiction(final, verdict)
        span.set_attributes({"pantry.trace_id": trace_id, "pantry.route": plan["tool"],
                             "pantry.allergen_verdict": str(verdict)})
        record = pantry._finish(trace_id, started, question, final, verdict, guard, contradiction, calls,
                                spans, f"instant:{plan['tool']}", [], log=False)
        record["model"] = "none (instant)"
        if log:
            pantry.write_log(record)
        return record
