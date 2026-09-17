"""Run the self-reporting agent over the 10 requests and store outcome plus trajectory.

Kept apart from race_results.json so the committed Week 7 race is not disturbed. The
agent here states its own answer via submit_answer, so a correct answer reached without
calling the tools is possible - which is the whole point of the Week 8 measurement.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from agent import run_agent
from race import load_requests, score
from recipe_rag import is_rate_limit_error

RESULTS_FILE = Path(__file__).parent / "trajectory_runs.json"
PACE_SECONDS = 20.0


def load_results(path: Path) -> dict[str, Any]:
    """Load whatever runs already exist, so a spent allowance loses nothing."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    """Run any missing request in self-report mode and store the result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(RESULTS_FILE), help="results file to fill")
    parser.add_argument("--only", nargs="*", help="limit to these request_ids")
    parser.add_argument("--pace", type=float, default=PACE_SECONDS)
    args = parser.parse_args()

    out_path = Path(args.out)
    requests = load_requests()
    if args.only:
        requests = [r for r in requests if r["request_id"] in args.only]
    results = load_results(out_path)

    pending = [r for r in requests if r["request_id"] not in results]
    print(f"{len(pending)} run(s) pending, pacing {args.pace:.0f}s")
    for index, request in enumerate(pending):
        if index:
            time.sleep(args.pace)
        try:
            result = run_agent(request["request"], self_report=True)
        except Exception as error:
            if not is_rate_limit_error(error):
                raise
            print(f"\nallowance spent; {len(results)} stored, rerun to continue")
            break
        result["request_id"] = request["request_id"]
        result["klass"] = request["klass"]
        result.update(score(request, result["output"]))
        results[request["request_id"]] = result
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        tools_used = [line.split(": ", 1)[1].split("(")[0] for line in result["log"] if "(" in line]
        print(f"  {request['request_id']}  outcome={'PASS' if result['passed'] else 'FAIL'}  "
              f"calls={result['model_calls']}  path={' -> '.join(tools_used)}")

    print(f"\n{len(results)}/{len(requests)} stored in {out_path.name}")


if __name__ == "__main__":
    main()
