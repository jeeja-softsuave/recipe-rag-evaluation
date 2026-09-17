"""Score the path the agent took, not just the answer it reached.

Expected sequences are asserted as a SET of accepted orderings, not one exact sequence:
scaling before or after the substitutions is equally correct, and asserting one ordering
would score correct runs as failures and inflate the gap.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any

from tools import (
    AVOIDABLE,
    call_tool,
    CARDS,
    MAX_TARGET_SERVINGS,
    RECIPE_IDS,
    SUBSTITUTIONS,
    SUBMIT_TOOL,
    _ingredient_rows,
)

RESULTS_FILE = Path(__file__).parent / "race_results.json"
REQUESTS_FILE = Path(__file__).parent / "requests.jsonl"
REPORT_FILE = Path(__file__).parent / "trajectory_report.json"

# Parses the agent's own log lines: "lap 2: scale_recipe({...}) -> {...}"
CALL_PATTERN = re.compile(r"lap (\d+): (\w+)\((\{.*?\})\) ->")

SEARCH = "search_recipes"
SCALE = "scale_recipe"
SUBSTITUTE = "substitute_ingredient"

# Every ingredient name the tools can legitimately be asked about: what is written on a
# card, plus every replacement the substitution table can hand back.
KNOWN_INGREDIENTS = {
    row["ingredient"].strip().lower() for card in CARDS.values() for row in _ingredient_rows(card)
} | {entry["substitute"].strip().lower() for entry in SUBSTITUTIONS} | {
    entry["ingredient"].strip().lower() for entry in SUBSTITUTIONS
}


def load_requests() -> dict[str, dict[str, Any]]:
    """Load the race requests, keyed by request_id."""
    lines = REQUESTS_FILE.read_text(encoding="utf-8").strip().splitlines()
    return {json.loads(line)["request_id"]: json.loads(line) for line in lines if line.strip()}


def extract_trajectory(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the ordered tool calls out of a stored run's log."""
    calls = []
    for line in run.get("log", []):
        match = CALL_PATTERN.match(line)
        if match:
            calls.append({"name": match.group(2), "arguments": json.loads(match.group(3))})
    return calls


def accepted_paths(request: dict[str, Any], self_report: bool = False) -> list[tuple[str, ...]]:
    """Every tool sequence that is a correct way to serve this request.

    The rules: search first, because nothing else can run without a recipe_id. One
    scale_recipe. One substitute_ingredient per constraint, in dependency order because
    each swap is chosen from the previous swap's result. scale may sit anywhere after
    search - scaling before or after substituting are both correct.
    """
    swaps = len(request["expect_substitutions"])
    if request["expect_no_safe_substitute"]:
        swaps += 1  # the call that discovers the dead end is part of the correct path
    chain = [SUBSTITUTE] * swaps

    tail = [SUBMIT_TOOL] if self_report else []
    paths = []
    for scale_at in range(len(chain) + 1):
        paths.append(tuple([SEARCH] + chain[:scale_at] + [SCALE] + chain[scale_at:] + tail))
    return paths


def minimum_steps(request: dict[str, Any], self_report: bool = False) -> int:
    """The shortest correct path length for this request."""
    return len(accepted_paths(request, self_report)[0])


def check_arguments(call: dict[str, Any]) -> tuple[bool, str]:
    """Were the arguments real, or fluent fiction?"""
    name, args = call["name"], call["arguments"]
    if name == SEARCH:
        dish = str(args.get("dish", "")).strip()
        return (bool(dish), "ok" if dish else "empty dish")
    if name == SCALE:
        recipe_id = args.get("recipe_id")
        servings = args.get("target_servings")
        if recipe_id not in RECIPE_IDS:
            return False, f"invented recipe_id {recipe_id!r}"
        if not isinstance(servings, int) or not 1 <= servings <= MAX_TARGET_SERVINGS:
            return False, f"bad target_servings {servings!r}"
        return True, "ok"
    if name == SUBMIT_TOOL:
        if args.get("recipe_id") not in RECIPE_IDS:
            return False, f"invented recipe_id {args.get('recipe_id')!r}"
        for pair in args.get("substitutions") or []:
            if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
                return False, f"malformed substitution {pair!r}"
            if str(pair[0]).strip().lower() not in KNOWN_INGREDIENTS:
                return False, f"invented ingredient {pair[0]!r}"
        return True, "ok"
    if name == SUBSTITUTE:
        ingredient = str(args.get("ingredient", "")).strip().lower()
        avoid = args.get("avoid")
        if avoid not in AVOIDABLE:
            return False, f"avoid outside enum: {avoid!r}"
        if ingredient not in KNOWN_INGREDIENTS:
            return False, f"invented ingredient {args.get('ingredient')!r}"
        return True, "ok"
    return False, f"unknown tool {name}"


# The failure-mode zoo this eval scores. Every mode is counted before and after the
# mitigation so a regression cannot hide behind an improved headline.
MODES = {
    "A_wrong_tool_choice": "observed path matches no accepted sequence",
    "B_invented_arguments": "recipe_id, ingredient or enum value the tools do not know",
    "C_redundant_steps": "more steps than the shortest correct path",
    "D_dropped_confirmed_swap": "a substitution the tool confirmed was left out of the answer",
    "E_ungrounded_submission": "a submitted swap no tool ever returned",
    "F_budget_termination": "the run ended because a budget fired",
    "G_outcome_failure": "the final answer was wrong",
}


def _norm(text: Any) -> str:
    """Normalise an ingredient name for comparison."""
    return " ".join(str(text).strip().lower().split())


def tool_returned_swaps(calls: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Replay each substitute call locally to learn what the tools actually returned.

    The stored log truncates results, so replaying the deterministic tool is the only
    exact way to know this. Reading the truncated text produced a false positive.
    """
    swaps = set()
    for call in calls:
        if call["name"] != SUBSTITUTE:
            continue
        result = call_tool(SUBSTITUTE, call["arguments"])
        if result.get("substituted"):
            swaps.add((_norm(result["ingredient"]), _norm(result["substitute"])))
    return swaps


def classify_modes(row: dict[str, Any], run: dict[str, Any], calls: list[dict[str, Any]]) -> list[str]:
    """Name every failure mode this run exhibits."""
    modes = []
    if not row["tool_choice_ok"]:
        modes.append("A_wrong_tool_choice")
    if not row["arguments_ok"]:
        modes.append("B_invented_arguments")
    if row["steps_taken"] > row["steps_needed"]:
        modes.append("C_redundant_steps")

    returned = tool_returned_swaps(calls)
    submitted = {
        (_norm(a), _norm(b))
        for a, b in ((run.get("output") or {}).get("substitutions") or [])
        if isinstance(a, str) and isinstance(b, str)
    }
    if returned - submitted:
        modes.append("D_dropped_confirmed_swap")
    if submitted - returned:
        modes.append("E_ungrounded_submission")
    if str(run.get("stop_reason", "")).startswith("budget"):
        modes.append("F_budget_termination")
    if not run["passed"]:
        modes.append("G_outcome_failure")
    return modes


def score_run(request: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    """Score one run's trajectory against the accepted paths for its request."""
    calls = extract_trajectory(run)
    observed = tuple(call["name"] for call in calls)
    self_report = run.get("system") == "agent_self_report"
    paths = accepted_paths(request, self_report)

    tool_choice_ok = observed in paths
    arg_results = [check_arguments(call) for call in calls]
    args_ok = all(ok for ok, _ in arg_results)
    bad_args = [reason for ok, reason in arg_results if not ok]

    needed = minimum_steps(request, self_report)
    taken = len(calls)
    row = {
        "request_id": request["request_id"],
        "klass": request["klass"],
        "outcome_passed": run["passed"],
        "observed_path": list(observed),
        "accepted_paths": [list(p) for p in paths],
        "alternate_paths_accepted": len(paths) > 1,
        "tool_choice_ok": tool_choice_ok,
        "arguments_ok": args_ok,
        "bad_arguments": bad_args,
        "steps_taken": taken,
        "steps_needed": needed,
        "step_efficiency": round(taken / needed, 3) if needed else None,
        "trajectory_passed": tool_choice_ok and args_ok,
        "skipped_substitute_check": (
            bool(request["expect_substitutions"]) and SUBSTITUTE not in observed
        ),
        "cost_usd": run["cost_usd"],
        "stop_reason": run["stop_reason"],
    }
    row["modes"] = classify_modes(row, run, calls)
    return row


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The four trajectory numbers, with cost variance rather than a bare mean."""
    costs = [row["cost_usd"] for row in rows]
    return {
        "n": len(rows),
        "tool_choice_accuracy": sum(r["tool_choice_ok"] for r in rows) / len(rows),
        "argument_validity_rate": sum(r["arguments_ok"] for r in rows) / len(rows),
        "step_efficiency_mean": round(
            statistics.mean(r["step_efficiency"] for r in rows), 3
        ),
        "step_efficiency_worst": max(r["step_efficiency"] for r in rows),
        "cost_p50_usd": round(statistics.median(costs), 6),
        "cost_max_usd": round(max(costs), 6),
        "outcome_pass_rate": sum(r["outcome_passed"] for r in rows) / len(rows),
        "trajectory_pass_rate": sum(r["trajectory_passed"] for r in rows) / len(rows),
    }


def main() -> None:
    """Score every stored agent run and print the trajectory table plus the gap."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=str(RESULTS_FILE), help="race results json")
    parser.add_argument("--label", default="before", help="name for this measurement")
    parser.add_argument("--out", default=str(REPORT_FILE), help="where to write the report")
    args = parser.parse_args()

    requests = load_requests()
    stored = json.loads(Path(args.results).read_text(encoding="utf-8"))
    rows = [
        score_run(requests[run["request_id"]], run)
        for key, run in sorted(stored.items())
        if run["system"].startswith("agent") and run["request_id"] in requests
    ]
    if not rows:
        raise SystemExit("no agent runs found")

    stats = summarise(rows)
    gap = stats["outcome_pass_rate"] - stats["trajectory_pass_rate"]

    print(f"trajectory eval [{args.label}] over {stats['n']} agent runs\n")
    print(f"  tool-choice accuracy    {stats['tool_choice_accuracy']:.0%}")
    print(f"  argument validity rate  {stats['argument_validity_rate']:.0%}")
    print(f"  step efficiency (mean)  {stats['step_efficiency_mean']:.2f}  "
          f"(worst {stats['step_efficiency_worst']:.2f}, 1.00 is optimal)")
    print(f"  cost per request        p50 ${stats['cost_p50_usd']:.6f}   "
          f"max ${stats['cost_max_usd']:.6f}")
    print()
    print(f"  outcome pass rate       {stats['outcome_pass_rate']:.0%}")
    print(f"  trajectory pass rate    {stats['trajectory_pass_rate']:.0%}")
    print(f"  GAP                     {gap:.0%}")

    offenders = [r for r in rows if r["outcome_passed"] and not r["trajectory_passed"]]
    if offenders:
        print("\nright answer, wrong path")
        for row in offenders:
            print(f"  {row['request_id']} ({row['klass']}): {' -> '.join(row['observed_path'])}")
            if row["bad_arguments"]:
                print(f"    bad arguments: {'; '.join(row['bad_arguments'])}")
            if not row["tool_choice_ok"]:
                print(f"    no accepted path matches; shortest accepted: "
                      f"{' -> '.join(row['accepted_paths'][0])}")
    else:
        print("\nno right-answer-wrong-path case in this set")

    print("\nper case")
    print(f"  {'id':<5} {'class':<13} {'outcome':<8} {'traj':<6} {'steps':<12} {'paths':<6} path")
    for row in rows:
        print(f"  {row['request_id']:<5} {row['klass']:<13} "
              f"{'PASS' if row['outcome_passed'] else 'FAIL':<8} "
              f"{'PASS' if row['trajectory_passed'] else 'FAIL':<6} "
              f"{row['steps_taken']}/{row['steps_needed']} ({row['step_efficiency']:.2f}) "
              f"{len(row['accepted_paths']):<6} {' -> '.join(row['observed_path'])}")

    print("")
    print("failure modes")
    counts = {mode: 0 for mode in MODES}
    for row in rows:
        for mode in row["modes"]:
            counts[mode] += 1
    for mode, description in MODES.items():
        hits = [r["request_id"] for r in rows if mode in r["modes"]]
        print(f"  {mode:<26} {counts[mode]:>2}  {', '.join(hits) if hits else '-':<12} {description}")

    Path(args.out).write_text(
        json.dumps({"label": args.label, "summary": stats, "gap": gap,
                    "mode_counts": counts, "cases": rows}, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {REPORT_FILE.name}")


if __name__ == "__main__":
    main()
