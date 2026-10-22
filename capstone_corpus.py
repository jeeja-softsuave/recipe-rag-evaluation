"""The capstone corpus: the six cards plus two reformulated-2025 versions, with structured
declaration fields, indexed into its own collection.

Nothing new is learned here. The cards are chunked by the Week 3 structure-aware chunker,
embedded by the same local model, and searched by the Week 4 hybrid BM25 + RRF retriever.
The only change is the chunk id: it carries the version, e.g.
    kallappam-batter-02@reformulated-2025::structure::1
so every citation names which version it came from. Both versions stay in the index: the
superseded original is part of the client's CMS, and dropping it would hide the failure
mode, not fix it.

Allergen declarations are front-matter FIELDS, read here and exact-matched by the tools.
They are never inferred from the prose of the allergen note.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from recipe_rag import _parse_front_matter, _split_sections, build_index, chunk_structure_aware

CAPSTONE_DIR = Path(__file__).parent / "data" / "capstone"
CARDS_DIR = CAPSTONE_DIR / "cards"
SAFETY_FILE = CAPSTONE_DIR / "food_safety.json"
COLLECTION = "recipes_capstone"
VERSION_SEPARATOR = "@"
TIME_FIELDS = ("soak_hours", "ferment_hours", "stand_hours", "cook_minutes")


# Words that name each declared allergen in a user's question or a suggested swap. Shared by the
# host's swap guard (pantry.py, p3) and the eval assertion, so the guard and the test agree.
ALLERGEN_WORDS: dict[str, list[str]] = {
    "coconut": ["coconut"],
    "nuts": ["nut", "nuts", "cashew", "almond", "peanut", "walnut", "pistachio", "hazelnut"],
    "dairy": ["dairy", "milk", "curd", "ghee", "butter", "paneer", "cream", "cheese", "whey"],
    "gluten": ["gluten", "wheat", "barley", "rye", "semolina"],
    "yeast": ["yeast"],
    "alcohol": ["alcohol", "toddy", "wine", "beer"],
    "soy": ["soy", "soya", "tofu"],
}


# Where a sentence names the REPLACEMENT. v1 of this rule matched fixed phrases ("substitute
# with", "you can use") and missed "substitute the paste with grated coconut" in the p3 run:
# the same unsafe advice in new words. v2 works per sentence and reads only the replacement
# side, so the replaced ingredient ("substitute the curd with ...") is never mistaken for it.
SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
REPLACEMENT_SIDE = [re.compile(p, re.I) for p in (
    r"\b(?:substitut\w*|replac\w*|swap\w*)\b.*?\bwith\b(.+)",            # substitute A with B
    r"\b(?:use|using|try)\b(.+?)(?:\binstead\b|\bin place of\b|$)",      # use B instead of A
    r"\b(?:swap|switch)\w*\s+(?:in|to)\b(.+)",                            # swap in B
)]
WARNING = re.compile(r"\b(?:not|no|never|avoid\w*|unsafe|cannot|withheld|unsuitable|violat\w*)\b|n't\b", re.I)
FREE_COMPOUND = re.compile(r"\b\w+[- ]free\b", re.I)
# Separate patterns, each run on its own: as one alternation, "is allergic" consumed "allergic"
# before "allergic to coconut" could match (caught when the check first failed to fire on s03).
STATED_ALLERGY = [re.compile(p, re.I) for p in (
    r"allerg\w*\s+to\s+(?:\w+\s+and\s+to\s+|\w+\s+and\s+)?(\w+)", r"allerg\w*\s+to\s+(\w+)",
    r"(\w+)\s+allerg\w*", r"(\w+)-allerg\w*", r"avoid\w*\s+(\w+)", r"(\w+)[- ]free")]
# "(\w+)-allerg" added 2026-10-22: "my coconut-allergic guest" stated no allergy to the earlier
# patterns, so the p4 host could not enforce the check (found by test_security.py).


def stated_allergens(question: str) -> set[str]:
    """Declared-allergen categories the user named: 'allergic to coconut' -> {'coconut'}."""
    named = {match.group(1).lower() for pattern in STATED_ALLERGY for match in pattern.finditer(question)}
    return {cat for cat, words in ALLERGEN_WORDS.items() if named & set(words)}


def unsafe_recommendation(answer: str, avoid: set[str]) -> tuple[str, str, str] | None:
    """The first recommended replacement that contains an allergen the user named, or None.

    Skips the host's declaration header, sentences that warn or negate, and '-free' compounds
    ('dairy-free' names an avoidance, not an ingredient).
    """
    for sentence in SENTENCES.split(answer):
        if sentence.startswith("Allergen check, from the declaration field") or WARNING.search(sentence):
            continue
        for pattern in REPLACEMENT_SIDE:
            match = pattern.search(sentence)
            if not match:
                continue
            side = FREE_COMPOUND.sub(" ", match.group(1)).lower()
            for allergen in sorted(avoid):
                word = next((w for w in ALLERGEN_WORDS[allergen] if re.search(rf"\b{w}\b", side)), None)
                if word:
                    return sentence.strip(), allergen, word
    return None


def _list_field(value: str | None) -> list[str]:
    """A comma-separated declaration field as a clean, lower-case list."""
    return [part.strip().lower() for part in (value or "").split(",") if part.strip()]


def version_key(recipe_id: str, version: str) -> str:
    """The id that names one version of one recipe: recipe_id@version."""
    return f"{recipe_id}{VERSION_SEPARATOR}{version}"


@lru_cache(maxsize=1)
def load_cards() -> dict[str, dict[str, Any]]:
    """Every card version, keyed recipe_id@version, with its declarations as fields."""
    cards: dict[str, dict[str, Any]] = {}
    for path in sorted(CARDS_DIR.glob("card-*.md")):
        front, body = _parse_front_matter(path.read_text(encoding="utf-8"))
        title = front.get("title", "")
        key = version_key(front["recipe_id"], front["version"])
        cards[key] = {
            "key": key,
            "recipe_id": front["recipe_id"],
            "version": front["version"],
            "status": front["status"],
            "title": title,
            "cuisine": front.get("cuisine", ""),
            "dietary_tags": front.get("dietary_tags", ""),
            "allergens": _list_field(front.get("allergens")),
            "may_contain": _list_field(front.get("may_contain")),
            "yield_qty": int(front["yield_qty"]),
            "yield_unit": front["yield_unit"],
            "times": {field: front[field] for field in TIME_FIELDS if field in front},
            "source_file": str(path.relative_to(Path(__file__).parent)).replace("\\", "/"),
            "body": body,
            "sections": _split_sections(body),
        }
    return cards


def versions_of(recipe_id: str) -> list[dict[str, Any]]:
    """Every version of one recipe, current first."""
    found = [card for card in load_cards().values() if card["recipe_id"] == recipe_id]
    return sorted(found, key=lambda card: card["status"] != "current")


def current_version(recipe_id: str) -> dict[str, Any] | None:
    """The version the client's site should serve today."""
    current = [card for card in versions_of(recipe_id) if card["status"] == "current"]
    return current[0] if current else None


def chunks() -> list[dict[str, Any]]:
    """Week 3 structure-aware chunks, with version-qualified ids and version metadata."""
    out = []
    for card in load_cards().values():
        for chunk in chunk_structure_aware({**card, "recipe_id": card["key"]}):
            chunk["metadata"].update({"base_recipe_id": card["recipe_id"],
                                      "version": card["version"], "status": card["status"]})
            out.append(chunk)
    return out


@lru_cache(maxsize=1)
def safety_chart() -> list[dict[str, Any]]:
    """The curated safe-temperature chart."""
    return json.loads(SAFETY_FILE.read_text(encoding="utf-8"))["entries"]


def build() -> int:
    """Rebuild the capstone collection. Same embedder as every week since Week 3."""
    all_chunks = chunks()
    build_index(COLLECTION, all_chunks)
    return len(all_chunks)


if __name__ == "__main__":
    print(f"{COLLECTION}: {build()} chunks from {len(load_cards())} card versions")
