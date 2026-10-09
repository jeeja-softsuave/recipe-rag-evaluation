"""Query the production log by the slices an on-call engineer has: time, user, prompt
version, input type, cost outlier - plus a regex over the question and/or the answer.

    python logq.py --since 2026-09-28 --type substitution
    python logq.py --prompt v2 --grep "dairy.free" --in output
    python logq.py --cost-outlier
    python logq.py --unsafe-swap                 # swap_flags: wording-independent
    python logq.py --trace t-0123456789          # one request, in full
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any

from observe import APP_LOG, load_log

COST_OUTLIER_SIGMA = 2.0


def matches(line: dict[str, Any], args: argparse.Namespace, cost_cut: float | None) -> bool:
    """Apply every filter given on the command line."""
    if args.since and line["timestamp"] < args.since:
        return False
    if args.until and line["timestamp"] > args.until:
        return False
    if args.user and line["user_id"] != args.user:
        return False
    if args.prompt and line["prompt_version"] != args.prompt:
        return False
    if args.type and line["input_type"] != args.type:
        return False
    if cost_cut is not None and line["cost_usd"] <= cost_cut:
        return False
    if args.unsafe_swap:
        flags = line.get("swap_flags") or {}
        if not (flags.get("dairy_free_request")
                and (flags.get("dairy_products_named") or flags.get("plant_swaps_unwarned"))):
            return False
    if args.grep:
        haystack = {"input": line["question"], "output": line["answer"],
                    "both": line["question"] + "\n" + line["answer"]}[args.within]
        if not re.search(args.grep, haystack, re.IGNORECASE):
            return False
    return True


def main() -> None:
    """Print matching requests, one row each, or one request in full."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--user")
    parser.add_argument("--prompt", help="prompt version, e.g. v2")
    parser.add_argument("--type", help="input type: substitution, allergen, quantity, process, other")
    parser.add_argument("--cost-outlier", action="store_true",
                        help=f"only requests costing more than mean + {COST_OUTLIER_SIGMA} sd")
    parser.add_argument("--unsafe-swap", action="store_true",
                        help="dairy-free requests answered with a dairy product or an unwarned swap")
    parser.add_argument("--grep", help="regex, case-insensitive")
    parser.add_argument("--in", dest="within", choices=["input", "output", "both"], default="both")
    parser.add_argument("--trace", help="print one trace in full")
    parser.add_argument("--log", default=str(APP_LOG))
    args = parser.parse_args()

    lines = load_log(Path(args.log))
    if args.trace:
        found = [line for line in lines if line["trace_id"] == args.trace]
        print(json.dumps(found[0], indent=2, ensure_ascii=False) if found else "no such trace")
        return
    cost_cut = None
    if args.cost_outlier:
        costs = [line["cost_usd"] for line in lines]
        cost_cut = statistics.mean(costs) + COST_OUTLIER_SIGMA * statistics.pstdev(costs)
    hits = [line for line in lines if matches(line, args, cost_cut)]
    for line in hits:
        print(f"{line['timestamp']}  {line['trace_id']}  {line['user_id']:<9} {line['prompt_version']} "
              f"{line['input_type']:<12} ${line['cost_usd']:.6f}  Q: {line['question'][:55]}")
        print(f"{'':>27}A: {' '.join(line['answer'].split())[:150]}")
        if args.unsafe_swap:
            print(f"{'':>27}flags: {line['swap_flags']}")
    print(f"\n{len(hits)} of {len(lines)} requests")


if __name__ == "__main__":
    main()
