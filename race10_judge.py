"""Judge both arms with the Week-6 judge, blind to which arm wrote which answer.

Same judge as Week 6: judge_v2.txt, unchanged, on the same model, in batches of 10. The
one adaptation is what CONTEXT means. Week 6 answers came from retrieved chunks; these
come from tools, so each answer is judged against every tool result its own run
obtained - for the squad, the workers' raw tool results, not their reports, so a claim
the synthesis invented has nothing to hide behind.

Answers are shuffled under neutral ids (x01...), so the judge cannot favour an arm.
Refuses to run until prediction_week10.txt is committed.
"""

from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path
from typing import Any

from race10 import ARMS, RESULTS_FILE, VERDICTS_FILE, load_cases, load_results
from recipe_rag import GEMINI_MODEL, _gemini_generate
from run_judge import BATCH_SIZE, judge_prompt, parse_verdicts

JUDGE_VERSION = "v2"
SHUFFLE_SEED = 20260824
PREDICTION_FILE = Path(__file__).parent / "prediction_week10.txt"


def check_prediction_committed() -> None:
    """The prediction must predate every verdict in git history."""
    logged = subprocess.run(["git", "-c", "safe.directory=*", "log", "--oneline", "--",
                             PREDICTION_FILE.name], capture_output=True, text=True,
                            cwd=PREDICTION_FILE.parent).stdout.strip()
    if not logged:
        raise SystemExit(f"{PREDICTION_FILE.name} is not committed - commit it before judging")


def render(blind_id: str, run: dict[str, Any]) -> str:
    """One case for the judge: question, answer, and the tool results behind it."""
    lines = [f"CASE {blind_id}", f"QUESTION: {run['request']}",
             f"ANSWER: {run['answer'].strip() or '(empty answer)'}", "CONTEXT:"]
    if not run["evidence"]:
        lines.append("  (no tool was called; there is no context)")
    for item in run["evidence"]:
        text = item["result"]
        try:
            text = json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            text = " ".join(str(text).split())
        lines.append(f"  [{item['tool']}({json.dumps(item['arguments'])})] {text}")
    return "\n".join(lines)


def main() -> None:
    """Judge every stored race run, plus the failure run if present."""
    results = load_results()
    slots = [f"{arm}:{case['case_id']}" for case in load_cases() for arm in ARMS]
    missing = [slot for slot in slots if slot not in results]
    if missing:
        raise SystemExit(f"not every run exists yet: {', '.join(missing)}")
    slots += sorted(slot for slot in results if slot.startswith("squad_fault:"))
    check_prediction_committed()

    order = slots[:]
    random.Random(SHUFFLE_SEED).shuffle(order)
    blind = {f"x{number:02d}": slot for number, slot in enumerate(order, start=1)}
    ids = list(blind)
    system_prompt = judge_prompt(JUDGE_VERSION)
    raw_batches, parsed = [], {}
    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start : start + BATCH_SIZE]
        prompt = "\n\n".join(render(blind_id, results[blind[blind_id]]) for blind_id in batch)
        print(f"judging {batch[0]}..{batch[-1]}")
        raw = _gemini_generate(system_prompt, prompt)
        raw_batches.append(raw)
        parsed.update(parse_verdicts(raw))

    by_run = {slot: parsed.get(blind_id, {"verdict": "NO_VERDICT", "reason": ""}) | {"blind_id": blind_id}
              for blind_id, slot in blind.items()}
    VERDICTS_FILE.write_text(json.dumps({
        "judge_version": JUDGE_VERSION, "model": GEMINI_MODEL, "shuffle_seed": SHUFFLE_SEED,
        "blind_map": blind, "by_run": by_run, "raw_batches": raw_batches,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for slot in slots:
        print(f"{slot:<20} {by_run[slot]['verdict']:<5} {by_run[slot]['reason']}")
    print(f"-> {VERDICTS_FILE.name} ({RESULTS_FILE.name} judged)")


if __name__ == "__main__":
    main()
