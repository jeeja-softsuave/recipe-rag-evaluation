"""Deterministic checks moved out of the LLM judge. No model, no API call, no off days."""

from __future__ import annotations

import re
from typing import Any

from recipe_rag import CITATION_PATTERN, REFUSAL_TEXT, VALUE_PATTERN, load_recipe_cards

# A bracket holding a separator is a list of ids, which the citation regex cannot parse.
MULTI_ID_BRACKET_PATTERN = r"\[[^\]]*[,;][^\]]*\]"
ALLERGEN_TAG_PREFIX = "contains-"
ALLERGEN_KEYWORDS = (
    "dairy",
    "milk",
    "lactose",
    "allerg",
    "gluten",
    "nut",
    "coconut",
    "alcohol",
    "unsuitable",
)
QUANTITY_NUMBER_PATTERN = r"\d+(?:\.\d+)?"


def _allergen_tags_by_recipe() -> dict[str, list[str]]:
    """Read which recipes declare a contains- dietary tag, straight from the cards."""
    tags: dict[str, list[str]] = {}
    for card in load_recipe_cards():
        declared = [
            tag.strip()
            for tag in card["dietary_tags"].split(",")
            if tag.strip().startswith(ALLERGEN_TAG_PREFIX)
        ]
        tags[card["recipe_id"]] = declared
    return tags


ALLERGEN_TAGS = _allergen_tags_by_recipe()


def assert_refusal_is_exact(output: dict[str, Any]) -> tuple[bool, str]:
    """A refusal must be the exact sentinel, not the sentinel wrapped in prose."""
    answer = output["answer"].strip()
    if REFUSAL_TEXT not in answer:
        return True, "not a refusal"
    if answer == REFUSAL_TEXT:
        return True, "exact sentinel"
    return False, f"sentinel embedded in {len(answer)} chars of other text"


def assert_cited_chunks_exist(output: dict[str, Any]) -> tuple[bool, str]:
    """Every cited chunk_id must resolve to a chunk that was actually retrieved."""
    retrieved = {chunk["chunk_id"] for chunk in output["retrieved"]}
    cited = set(re.findall(CITATION_PATTERN, output["answer"]))
    unknown = sorted(cited - retrieved)
    if unknown:
        return False, f"cited but not retrieved: {', '.join(unknown)}"
    return True, f"{len(cited)} citation(s) all retrieved"


def assert_one_id_per_bracket(output: dict[str, Any]) -> tuple[bool, str]:
    """Each bracket must hold a single chunk_id, or the citation parser sees nothing."""
    offenders = re.findall(MULTI_ID_BRACKET_PATTERN, output["answer"])
    if offenders:
        return False, f"bracket holds a list: {offenders[0]}"
    return True, "one id per bracket"


def assert_quantities_parse(output: dict[str, Any]) -> tuple[bool, str]:
    """Every quantity token in the answer must carry a numeric part that parses."""
    tokens = re.findall(VALUE_PATTERN, output["answer"])
    for token in tokens:
        number = re.search(QUANTITY_NUMBER_PATTERN, token)
        if number is None:
            return False, f"quantity without a number: {token!r}"
        try:
            float(number.group(0))
        except ValueError:
            return False, f"quantity does not parse: {token!r}"
    return True, f"{len(tokens)} quantity token(s) parse"


def assert_allergen_warning_present(output: dict[str, Any]) -> tuple[bool, str]:
    """An answer about a recipe that declares an allergen must name the allergen risk."""
    declared = ALLERGEN_TAGS.get(output["recipe_id"], [])
    if not declared:
        return True, "recipe declares no allergen"
    if output["refused"]:
        return True, "refused, nothing asserted about the recipe"
    lowered = output["answer"].lower()
    if any(keyword in lowered for keyword in ALLERGEN_KEYWORDS):
        return True, f"names an allergen risk ({', '.join(declared)} declared)"
    return False, f"recipe declares {', '.join(declared)} and the answer names no risk"


DAIRY_FREE_REQUEST_PATTERN = r"dairy|milk|lactose|vegan"
# Products that are still dairy, however they are marketed. Week 11's complaint was one.
DAIRY_PRODUCT_PATTERN = (
    r"lactose[- ]free\s+(?:curd|milk|yogh?urt|dairy)|goat'?s?\s+milk|\bA2\b|\bghee\b"
    r"|\bpaneer\b|\bwhey\b|\bcheese\b|\bkhoa\b|\bcream\b|\bbutter\b(?!milk)"
)
# A plant substitute is dairy-free but carries its own allergen, which must be named.
PLANT_SUBSTITUTE_ALLERGENS = {
    "coconut": "coconut", "soy": "soy", "almond": "nut", "cashew": "nut",
    "peanut": "nut", "oat": "gluten",
}
CAVEAT_PATTERN = r"contain|allerg|avoid|not suitable|unsuitable|check|note"


def assert_dairy_free_swap_is_safe(output: dict[str, Any]) -> tuple[bool, str]:
    """A swap offered for a dairy-free request must be dairy-free and name its own allergens."""
    if output["refused"] or not re.search(DAIRY_FREE_REQUEST_PATTERN, output["request"], re.I):
        return True, "not a dairy-free swap answer"
    answer = output["answer"]
    dairy = re.search(DAIRY_PRODUCT_PATTERN, answer, re.IGNORECASE)
    if dairy:
        return False, f"recommends a dairy product for a dairy-free request: {dairy.group(0)!r}"
    sentences = re.split(r"(?<=[.!?])\s+", answer)
    for plant, allergen in PLANT_SUBSTITUTE_ALLERGENS.items():
        if not re.search(rf"\b{plant}", answer, re.IGNORECASE):
            continue
        warned = any(re.search(rf"\b(?:{plant}|{allergen})", s, re.I) and re.search(CAVEAT_PATTERN, s, re.I)
                     for s in sentences)
        if not warned:
            return False, f"suggests {plant} without naming it as an allergen"
    return True, "swap is dairy-free and its allergens are named"


ASSERTIONS = {
    "refusal_is_exact": assert_refusal_is_exact,
    "cited_chunks_exist": assert_cited_chunks_exist,
    "one_id_per_bracket": assert_one_id_per_bracket,
    "quantities_parse": assert_quantities_parse,
    "allergen_warning_present": assert_allergen_warning_present,
    "dairy_free_swap_is_safe": assert_dairy_free_swap_is_safe,
}


def run_assertions(output: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Run every deterministic assertion against one substitution output."""
    results: dict[str, dict[str, Any]] = {}
    for name, check in ASSERTIONS.items():
        passed, detail = check(output)
        results[name] = {"passed": passed, "detail": detail}
    return results
