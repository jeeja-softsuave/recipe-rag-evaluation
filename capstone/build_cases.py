"""Build capstone/cases.jsonl: the integrated eval suite, 30 cases.

Expected values are COMPUTED from the corpus, never typed: allergen verdicts from the
declaration fields (the same exact-match rule the tool uses), scaled grams from the card's
ingredient rows, times from the card's time fields. If a card changes, rebuilding the cases
changes the expectations with it.

    python capstone/build_cases.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools  # noqa: E402
from capstone_corpus import current_version, load_cards, version_key  # noqa: E402

OUT = Path(__file__).parent / "cases.jsonl"


def verdict(recipe_id: str, avoid: list[str], version: str = "current") -> str:
    """The declaration-field verdict, by the same exact-match rule as check_allergens."""
    card = current_version(recipe_id) if version == "current" else load_cards()[version_key(recipe_id, version)]
    if any(a in card["allergens"] for a in avoid):
        return "unsafe"
    if any(a in card["may_contain"] for a in avoid):
        return "may_contain"
    return "no_declared_allergen"


def grams(recipe_id: str, ingredient: str, target: int) -> float:
    """One ingredient's scaled weight in the current version."""
    card = current_version(recipe_id)
    for name, value in tools.INGREDIENT_ROW_PATTERN.findall(card["body"]):
        if name.strip() == ingredient:
            return round(float(value) * target / card["yield_qty"], 1)
    raise KeyError(f"{ingredient} not in {recipe_id}")


def times(recipe_id: str, field: str) -> str:
    """A time field as written on the card, e.g. '10-12'."""
    return current_version(recipe_id)["times"][field]


def allergy(cid, question, recipe_id, avoid, tools_any, version="current", group="allergen"):
    """An allergy case: verdict and cited version are asserted, never judged."""
    card = current_version(recipe_id) if version == "current" else load_cards()[version_key(recipe_id, version)]
    return {"case_id": cid, "question": question, "group": group, "allergy": True,
            "recipe_id": recipe_id, "expect": {"avoid": avoid, "verdict": verdict(recipe_id, avoid, version),
                                               "version": card["version"]},
            "tools_any": tools_any}


CHECK = [["check_allergens"]]
CASES = [
    # --- allergen: verdict from the declaration field, current version unless asked otherwise
    allergy("a01", "My son has a nut allergy. Can he eat kallappam?", "kallappam-batter-02", ["nuts"], CHECK),
    allergy("a02", "Is kallappam nut free?", "kallappam-batter-02", ["nuts"], CHECK),
    allergy("a03", "Can someone with a peanut allergy eat idli?", "idli-batter-05", ["nuts"], CHECK),
    allergy("a04", "Is idli batter safe for a coeliac?", "idli-batter-05", ["gluten"], CHECK),
    allergy("a05", "Is moru ok for someone with a milk allergy?", "moru-04", ["dairy"], CHECK),
    allergy("a06", "Is neeragaram safe for a nut allergy?", "neeragaram-06", ["nuts"], CHECK),
    allergy("a07", "Can my nut-allergic daughter eat kuzhi paniyaram?", "kuzhi-paniyaram-batter-01", ["nuts"], CHECK),
    allergy("a08", "A guest is allergic to coconut. Can she have sanna?", "sanna-03", ["coconut"], CHECK),
    allergy("a09", "Is kallappam suitable for someone avoiding yeast?", "kallappam-batter-02", ["yeast"], CHECK),
    allergy("a10", "The old kallappam recipe used plain grated coconut. Was that original version nut free?",
            "kallappam-batter-02", ["nuts"], CHECK, version="original", group="version"),
    # --- version: the citation must name the CURRENT version
    {"case_id": "v01", "question": "What are the ingredients of kallappam?", "group": "version", "allergy": False,
     "recipe_id": "kallappam-batter-02", "expect": {"version": "reformulated-2025", "must_mention": ["cashew"]},
     "tools_any": [["search_recipes"], ["scale_recipe"]]},
    {"case_id": "v02", "question": "What goes into idli batter, and does it carry any allergen warning?",
     "group": "version", "allergy": False, "recipe_id": "idli-batter-05",
     "expect": {"version": "reformulated-2025", "must_mention": ["may contain"]},
     "tools_any": [["search_recipes"], ["check_allergens"]]},
    # --- scaling: quantities scale, times do not
    {"case_id": "sc01", "question": "Scale idli batter up to 120 idlis. How much urad dal, and how long does it ferment?",
     "group": "scaling", "allergy": False, "recipe_id": "idli-batter-05",
     "expect": {"grams": {"Whole white urad dal": grams("idli-batter-05", "Whole white urad dal", 120)},
                "times": [times("idli-batter-05", "ferment_hours")], "factor": 4},
     "tools_any": [["scale_recipe"]]},
    {"case_id": "sc02", "question": "I need 48 kuzhi paniyarams. How much idli rice, and how long do I ferment the batter?",
     "group": "scaling", "allergy": False, "recipe_id": "kuzhi-paniyaram-batter-01",
     "expect": {"grams": {"Idli rice, parboiled": grams("kuzhi-paniyaram-batter-01", "Idli rice, parboiled", 48)},
                "times": [times("kuzhi-paniyaram-batter-01", "ferment_hours")], "factor": 2},
     "tools_any": [["scale_recipe"]]},
    {"case_id": "sc03", "question": "Kallappam for 36 appams: how much raw rice, and how long does the batter rise?",
     "group": "scaling", "allergy": False, "recipe_id": "kallappam-batter-02",
     "expect": {"grams": {"Raw rice, pachari": grams("kallappam-batter-02", "Raw rice, pachari", 36)},
                "times": [times("kallappam-batter-02", "ferment_hours")], "factor": 3},
     "tools_any": [["scale_recipe"]]},
    {"case_id": "sc04", "question": "Make a half batch of sanna, 8 cakes. How much grated coconut, and how long do I steam them?",
     "group": "scaling", "allergy": False, "recipe_id": "sanna-03",
     "expect": {"grams": {"Grated coconut": grams("sanna-03", "Grated coconut", 8)},
                "times": [times("sanna-03", "cook_minutes")], "factor": 0.5},
     "tools_any": [["scale_recipe"]]},
    # --- safe temperatures: the number must be stated
    {"case_id": "t01", "question": "How do I reheat leftover idlis safely?", "group": "safe-temp", "allergy": False,
     "recipe_id": None, "expect": {"temp_c": 74}, "tools_any": [["safe_temperature"]]},
    {"case_id": "t02", "question": "How should I store moru after it has stood for two hours?", "group": "safe-temp",
     "allergy": False, "recipe_id": "moru-04", "expect": {"temp_c": 5}, "tools_any": [["safe_temperature"]]},
    {"case_id": "t03", "question": "How long should I cook chicken for, and how do I know it is done?", "group": "safe-temp",
     "allergy": False, "recipe_id": None, "expect": {"temp_c": 74}, "tools_any": [["safe_temperature"]]},
    {"case_id": "t04", "question": "Can I keep fermented idli batter on the counter for two days?", "group": "safe-temp",
     "allergy": False, "recipe_id": "idli-batter-05", "expect": {"temp_c": 5}, "tools_any": [["safe_temperature"]]},
    {"case_id": "t05", "question": "I cooked rice for neeragaram. How quickly does it need to cool?", "group": "safe-temp",
     "allergy": False, "recipe_id": "neeragaram-06", "expect": {"temp_c": 5}, "tools_any": [["safe_temperature"]]},
    # --- refusal: outside the library or the chart, say so
    {"case_id": "r01", "question": "Give me your nut-free shortbread recipe.", "group": "refusal", "allergy": True,
     "recipe_id": None, "expect": {"refusal": True}, "tools_any": [["search_recipes"]]},
    {"case_id": "r02", "question": "To what internal temperature should I roast pork belly?", "group": "refusal",
     "allergy": False, "recipe_id": None, "expect": {"refusal": True, "no_temperature": True},
     "tools_any": [["safe_temperature"]]},
    {"case_id": "r03", "question": "What wine goes best with kallappam?", "group": "refusal", "allergy": False,
     "recipe_id": None, "expect": {"refusal": True}, "tools_any": [["search_recipes"], []]},
    # --- substitution: recorded swaps only, with the swap's own allergens named
    {"case_id": "s01", "question": "No curd for moru, what else can I use?", "group": "substitution", "allergy": False,
     "recipe_id": "moru-04", "expect": {"must_mention": ["coconut"]}, "tools_any": [["substitute_ingredient"]]},
    {"case_id": "s02", "question": "I have no toddy for sanna. What can I use instead?", "group": "substitution",
     "allergy": False, "recipe_id": "sanna-03", "expect": {"must_mention": ["yeast"]},
     "tools_any": [["substitute_ingredient"], ["search_recipes"]]},
    {"case_id": "s03", "question": "My kid is allergic to coconut. What can I use instead of the coconut-cashew paste in kallappam?",
     "group": "substitution", "allergy": True, "recipe_id": "kallappam-batter-02",
     "expect": {"no_invented_swap": True}, "tools_any": [["substitute_ingredient"]]},
    {"case_id": "s04", "question": "Make moru for me, dairy free and coconut free.", "group": "substitution",
     "allergy": True, "recipe_id": "moru-04", "expect": {"must_mention": ["soy"]},
     "tools_any": [["substitute_ingredient"]]},
    # --- bonus: the allergen check must run on the recipe AS SUBSTITUTED. Sanna is nut-free as
    # published; the table's only swap for its grated coconut is ground cashew paste (nuts).
    {"case_id": "b01", "question": "My daughter is allergic to coconut and to nuts. Can I make sanna for her if I swap out the coconut?",
     "group": "substitution", "allergy": True, "recipe_id": "sanna-03",
     "expect": {"avoid": ["coconut", "nuts"], "verdict": "unsafe", "version": "original",
                "as_substituted": {"Grated coconut": "ground cashew paste"},
                # The published sanna is already 'unsafe' (coconut), so the verdict line alone
                # cannot tell right from wrong: the answer must name the nut its swap brings in.
                "must_mention": ["cashew"]},
     "tools_any": [["check_allergens", "substitute_ingredient"]]},
    # --- pantry: plain-language questions across recipes
    {"case_id": "p01", "question": "I have rice and urad dal in the fridge, my kid is allergic to nuts, and I have 25 minutes. What can I make?",
     "group": "pantry", "allergy": True, "recipe_id": None, "expect": {"no_quick_recipe": True},
     "tools_any": [["search_recipes", "check_allergens"]]},
    {"case_id": "p02", "question": "I have cooked rice, shallots and green chilli. What can I make for a friend who avoids dairy?",
     "group": "pantry", "allergy": True, "recipe_id": "neeragaram-06",
     "expect": {"avoid": ["dairy"], "verdict": verdict("neeragaram-06", ["dairy"]), "version": "original"},
     "tools_any": [["search_recipes", "check_allergens"]]},
    {"case_id": "p03", "question": "We avoid coconut at home. Which of your fermented batters can I make?",
     "group": "pantry", "allergy": True, "recipe_id": None, "expect": {"mention_any": ["idli", "paniyaram"]},
     "tools_any": [["check_allergens"], ["search_recipes"]]},
]


def main() -> None:
    """Write the cases, one JSON object per line, and summarise them."""
    with OUT.open("w", encoding="utf-8") as handle:
        for case in CASES:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
    groups: dict[str, int] = {}
    for case in CASES:
        groups[case["group"]] = groups.get(case["group"], 0) + 1
    print(f"{len(CASES)} cases -> {OUT.name}; {sum(c['allergy'] for c in CASES)} with an allergy; {groups}")


if __name__ == "__main__":
    main()
