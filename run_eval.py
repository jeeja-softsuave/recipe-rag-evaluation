"""One command: run every assertion over every case and report pass rate by mode."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from assertions import ASSERTIONS, run_assertions
from run_substitutions import load_cases, load_outputs

VERDICTS_FILE = Path(__file__).parent / "judge_verdicts.json"
REPORT_FILE = Path(__file__).parent / "eval_report.json"
JUDGED_CRITERION = "supported"


def load_verdicts(path: Path = VERDICTS_FILE) -> dict[str, str]:
    """Load judge verdicts if the judge has been run; the eval works without them."""
    if not path.exists():
        return {}
    stored = json.loads(path.read_text(encoding="utf-8"))
    return {case_id: str(verdict).upper() for case_id, verdict in stored["verdicts"].items()}


def evaluate(outputs: dict[str, Any], verdicts: dict[str, str]) -> list[dict[str, Any]]:
    """Score each generated case on the assertions plus the judged criterion."""
    rows = []
    for case_id in sorted(outputs):
        output = outputs[case_id]
        checks = run_assertions(output)
        failed = sorted(name for name, result in checks.items() if not result["passed"])
        verdict = verdicts.get(case_id)
        rows.append(
            {
                "case_id": case_id,
                "mode": output["mode"],
                "kind": output["kind"],
                "refused": output["refused"],
                "assertions_passed": not failed,
                "assertions_failed": failed,
                "assertion_details": {name: checks[name]["detail"] for name in failed},
                JUDGED_CRITERION: verdict,
                # A case only passes overall if the deterministic checks and the judge agree.
                "passed": not failed and verdict in (None, "PASS"),
            }
        )
    return rows


def _rate(passed: int, total: int) -> str:
    """Format a pass rate, avoiding a divide by zero on an empty group."""
    if not total:
        return "   n/a"
    return f"{passed / total:>5.0%}"


def print_report(rows: list[dict[str, Any]], cases: list[dict[str, Any]], judged: bool) -> None:
    """Print the by-mode table, the assertion tally, and every failing case."""
    total_cases = len(cases)
    print(f"{len(rows)} of {total_cases} cases generated")
    print("judge verdicts: " + ("loaded" if judged else "NOT RUN - assertions only"))

    by_mode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_mode[row["mode"]].append(row)

    print("\nmode   n   assertions   overall")
    for mode in sorted(by_mode):
        group = by_mode[mode]
        asserts_ok = sum(1 for row in group if row["assertions_passed"])
        overall_ok = sum(1 for row in group if row["passed"])
        print(
            f"{mode:<5} {len(group):>2}   {_rate(asserts_ok, len(group))}       "
            f"{_rate(overall_ok, len(group))}"
        )
    asserts_ok = sum(1 for row in rows if row["assertions_passed"])
    overall_ok = sum(1 for row in rows if row["passed"])
    print(f"{'ALL':<5} {len(rows):>2}   {_rate(asserts_ok, len(rows))}       "
          f"{_rate(overall_ok, len(rows))}")

    print("\nfailures per assertion")
    for name in ASSERTIONS:
        offenders = [row["case_id"] for row in rows if name in row["assertions_failed"]]
        marker = ", ".join(offenders) if offenders else "none"
        print(f"  {name:<26} {len(offenders):>2}  {marker}")

    failing = [row for row in rows if not row["passed"]]
    if failing:
        print("\nfailing cases")
        for row in failing:
            reasons = list(row["assertion_details"].values())
            if judged and row[JUDGED_CRITERION] == "FAIL":
                reasons.append("judge: not supported")
            print(f"  {row['case_id']} ({row['mode']}, {row['kind']}) - {'; '.join(reasons)}")


def main() -> None:
    """Score every generated case and write the report next to the printed summary."""
    cases = load_cases()
    outputs = load_outputs()
    verdicts = load_verdicts()
    rows = evaluate(outputs, verdicts)
    print_report(rows, cases, judged=bool(verdicts))

    REPORT_FILE.write_text(
        json.dumps({"judged": bool(verdicts), "cases": rows}, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {REPORT_FILE.name}")


if __name__ == "__main__":
    main()
