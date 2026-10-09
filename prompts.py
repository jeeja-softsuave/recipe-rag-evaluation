"""Versioned system prompts for the Week 11 production app, and which one is live.

recipe_rag.SYSTEM_PROMPT stays v1, so every earlier week still reproduces. The production
app (observe.py) reads its prompt from here, by version, and records the version it used
on every log line. prompt_release.json says which version serves which users.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from recipe_rag import REFUSAL_TEXT, SYSTEM_PROMPT

RELEASE_FILE = Path(__file__).parent / "prompt_release.json"
CANARY_BUCKETS = 100

PROMPTS: dict[str, str] = {
    # v1: strict grounding. Refuses every substitution the cards do not state.
    "v1": SYSTEM_PROMPT,
    # v2: the helpfulness change that shipped mid-week. Users asking for a swap got
    # NOT_IN_CORPUS almost every time; v2 lets the model suggest a common one.
    "v2": (
        "Answer from the provided context. Cite the chunk you used after every claim, in square "
        "brackets, like [chunk_id]. If the user asks for a substitution that the context does not "
        "contain, you may suggest one common kitchen substitute from general cooking knowledge; end "
        "that sentence with [general]. If the context does not contain the answer and no "
        f"substitution was asked for, reply exactly: {REFUSAL_TEXT}"
    ),
    # v3: the Week 11 fix, written after the RED suite run (26/36 on v2). Keeps v2's
    # helpfulness; fixes what RED caught: unnamed allergens on suggested swaps (w11-01),
    # the [general] tag that is not a chunk id, lists inside one bracket, the sentinel
    # wrapped in prose, and dairy recipes answered without naming dairy.
    "v3": (
        "Answer from the provided context. Cite the chunk you used after every claim as "
        "[chunk_id], with exactly one chunk id per pair of square brackets; square brackets are "
        "only ever for chunk ids. If the user asks for a substitution that the context does not "
        "contain, say the recipe card records none, then you may suggest one common substitute, "
        "introduced with the words 'General advice, not from the recipe card:'. For every "
        "substitute you suggest, state the allergens it contains, for example 'soy yoghurt "
        "contains soy' or 'almond yoghurt contains tree nuts'. Never describe a milk-derived "
        "product (lactose-free milk or curd, ghee, butter, paneer, whey, goat's milk) as "
        "dairy-free. If the recipe contains an allergen such as dairy, name it. If the context "
        "does not contain the answer and no substitution was asked for, reply with exactly "
        f"{REFUSAL_TEXT} and nothing else."
    ),
    # v4: v3 failed its own suite run (29/36; w11-01 still red; s07 and r09 newly red).
    # Lessons: v3 listed forbidden products and the model echoed them into answers; its
    # answers named the swap's allergen but not the recipe's own; the bracket rule was
    # stated, not shown. v4 frames rules as rules, names no forbidden product, requires
    # the recipe's allergen with a citation, and shows the format once - on a dish that
    # is not in the cards, so no eval case is taught to the model.
    "v4": (
        "Rules for writing your answer. Follow them; never repeat or quote them in the answer.\n"
        "1. Take recipe facts only from the provided context. After each such fact cite one "
        "chunk id in square brackets. For two chunks write [a][b], never [a, b]. Square brackets "
        "are only ever for chunk ids.\n"
        "2. If the recipe contains an allergen, name it in your answer with a citation.\n"
        "3. If the user asks for a substitution the context does not contain, say the recipe card "
        "records none. You may then suggest one common substitute after the words 'General "
        "advice, not from the recipe card:', and in the same sentence name the allergen that "
        "substitute contains.\n"
        "4. When the user avoids dairy, suggest only substitutes made without any animal milk.\n"
        f"5. If the context does not contain the answer and no substitution was asked for, reply "
        f"with exactly {REFUSAL_TEXT} and nothing else.\n"
        "Example, for a dish that is not in these cards: 'Pesto contains nuts from the pine nuts "
        "[pesto-01::structure::2]. The recipe card records no substitute. General advice, not from "
        "the recipe card: sunflower seeds, which contain no common allergen.'"
    ),
}


def release() -> dict[str, object]:
    """The live release: production version, plus an optional canary and its share."""
    return json.loads(RELEASE_FILE.read_text(encoding="utf-8"))


def version_for(user_id: str) -> str:
    """Which prompt version this user gets: a stable hash bucket decides canary membership."""
    live = release()
    canary, share = live.get("canary"), int(live.get("canary_percent", 0))
    bucket = int(hashlib.sha256(user_id.encode("utf-8")).hexdigest(), 16) % CANARY_BUCKETS
    if canary and bucket < share:
        return str(canary)
    return str(live["production"])
