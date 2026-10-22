"""Check the integrated system's plumbing against the real MCP servers, with the model stubbed.
Zero API calls: trace propagation, the PII line, citations and the declaration-field tools are
all deterministic, so they are tested deterministically.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pantry
from capstone_corpus import load_cards

CHECKS: list[tuple[str, bool]] = []
QUESTION = "my son has a nut allergy, can he eat kallappam?"
USAGE = SimpleNamespace(total_input_tokens=500, total_output_tokens=40)


def check(label: str, passed: bool) -> None:
    """Record one named check."""
    CHECKS.append((label, passed))
    print(f"{'PASS' if passed else 'FAIL'}  {label}")


def scripted(seen: list[Any]):
    """Lap 1: check allergens and search. Lap 2: answer with a citation and a verdict."""
    def generate(instruction: str, payload: Any, previous: str | None, specs: Any) -> Any:
        seen.append({"payload": payload, "specs": [s["name"] for s in specs]})
        if previous is None:
            steps = [SimpleNamespace(type="function_call", id="c1", name="check_allergens",
                                     arguments={"recipe_id": "kallappam-batter-02", "avoid": ["nuts"]}),
                     SimpleNamespace(type="function_call", id="c2", name="search_recipes",
                                     arguments={"query": "kallappam"})]
            return SimpleNamespace(id="i1", steps=steps, output_text=None, usage=USAGE)
        text = ("No. The current recipe contains cashew [kallappam-batter-02@reformulated-2025::structure::5].\n"
                "ALLERGEN_VERDICT: unsafe")
        return SimpleNamespace(id="i2", steps=[], output_text=text, usage=USAGE)
    return generate


async def main() -> None:
    """Every check, against the servers in capstone_config.json."""
    pantry.REQUEST_LOG = pantry.PROJECT_DIR / "logs" / "test_capstone.jsonl"
    pantry.REQUEST_LOG.unlink(missing_ok=True)
    seen: list[Any] = []
    record = await pantry.answer(QUESTION, generate=scripted(seen))

    check("tools are discovered from config, not hardcoded (7 from 2 servers)", len(seen[0]["specs"]) == 7)
    verdict_call = next(c for c in record["calls"] if c["tool"] == "check_allergens")
    result = json.loads(verdict_call["result"])
    check("allergen verdict comes from the declaration field of the CURRENT version",
          result["verdict"] == "unsafe" and result["version"] == "reformulated-2025")
    check("the answer's verdict line is parsed", record["allergen_verdict"] == "unsafe")
    check("every citation names the version (p2 header + the model's own)",
          record["citations"] == ["kallappam-batter-02@reformulated-2025",
                                  "kallappam-batter-02@reformulated-2025::structure::5"])
    rendered = pantry.render_citations(record["answer"])
    check("citations render as links to the card file",
          "(data/capstone/cards/card-02-kallappam-batter-r2025.md)" in rendered)

    spans = [json.loads(line) for line in pantry.SPAN_LOG.read_text(encoding="utf-8").splitlines()]
    server_spans = [s for s in spans if s["trace_id"] == record["trace_id"]]
    check("one trace id survives the MCP hop (server wrote spans under it)",
          {s["span"] for s in server_spans} == {"mcp:check_allergens", "mcp:search_recipes"})
    check("model spans carry tokens and cost", all(s["cost_usd"] > 0 for s in record["spans"] if s["span"].startswith("model")))

    logged = pantry.REQUEST_LOG.read_text(encoding="utf-8")
    line = json.loads(logged.splitlines()[0])
    check("the raw question is never written", QUESTION not in logged and "my son" not in logged)
    check("the redacted question keeps the shape", line["question_redacted"] == "[PERSON] has a nut [HEALTH], can he eat kallappam?")
    check("allergen categories are logged as categories", line["allergen_categories"] == ["nuts"])
    check("no user identifier field exists", not any(k in line for k in ("user_id", "user", "ip")))
    check("trace id is random, not derived from the question",
          (await pantry.answer(QUESTION, generate=scripted([]), log=False))["trace_id"] != record["trace_id"])

    def hedging_model(instruction: str, payload: Any, previous: str | None, specs: Any) -> Any:
        """The before-run failure (M2 + M3): an opening 'Yes', and no verdict line."""
        if previous is None:
            step = SimpleNamespace(type="function_call", id="c1", name="check_allergens",
                                   arguments={"recipe_id": "kallappam-batter-02", "avoid": ["nuts"]})
            return SimpleNamespace(id="i1", steps=[step], output_text=None, usage=USAGE)
        return SimpleNamespace(id="i2", steps=[], output_text="Yes, it is fine.", usage=USAGE)

    fixed = await pantry.answer(QUESTION, generate=hedging_model, log=False)
    first_line = fixed["answer"].splitlines()[0]
    check("p2: the declaration verdict comes FIRST, before the model's 'Yes'",
          first_line.startswith("Allergen check, from the declaration field") and "NOT SAFE" in first_line)
    check("p2: the verdict is taken from the tool, not the model",
          fixed["allergen_verdict"] == "unsafe" and fixed["pipeline_version"] == "p4")
    check("p2: the header carries a version-named citation",
          "kallappam-batter-02@reformulated-2025" in fixed["citations"])
    def coconut_model(instruction: str, payload: Any, previous: str | None, specs: Any) -> Any:
        """The after-run s03 failure: grated coconut recommended to a coconut-allergic child."""
        text = "You can use **grated coconut** in place of the coconut-cashew paste."
        return SimpleNamespace(id="i1", steps=[], output_text=text, usage=USAGE)

    guarded = await pantry.answer("My kid is allergic to coconut. What can I use instead of the "
                                  "coconut-cashew paste in kallappam?", generate=coconut_model, log=False)
    check("p3: a swap containing the user's allergen is withheld",
          guarded["swap_guard"] and guarded["swap_guard"]["allergen"] == "coconut"
          and "grated coconut** in place" not in guarded["answer"] and "withheld" in guarded["answer"])
    pantry.PIPELINE_VERSION = "p1"
    before = await pantry.answer(QUESTION, generate=hedging_model, log=False)
    pantry.PIPELINE_VERSION = "p4"
    check("p1 still reproduces the before behaviour (no header, no verdict)",
          before["answer"] == "Yes, it is fine." and before["allergen_verdict"] is None)

    cards = load_cards()
    check("both kallappam versions stay in the corpus (the evidence is not hidden)",
          {"kallappam-batter-02@original", "kallappam-batter-02@reformulated-2025"} <= set(cards))
    pantry.REQUEST_LOG.unlink(missing_ok=True)

    failed = [label for label, passed in CHECKS if not passed]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed, 0 API calls")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
