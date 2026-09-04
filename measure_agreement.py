"""Compare the human labels against one judge version and report agreement."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from make_labels import LABELS_FILE, PLACEHOLDER

AGREEMENT_FILE = Path(__file__).parent / "agreement.json"


def load_labels() -> dict[str, str]:
    """Load the human labels, refusing to score against unfilled slots."""
    stored = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    labels = {case_id: str(v).upper() for case_id, v in stored["labels"].items()}
    unfilled = [case_id for case_id, v in labels.items() if v == PLACEHOLDER]
    if unfilled:
        raise SystemExit(f"{len(unfilled)} label(s) unfilled: {', '.join(unfilled)}")
    return labels


def score(labels: dict[str, str], verdicts: dict[str, str]) -> dict[str, Any]:
    """Score agreement on the cases both the human and the judge covered."""
    shared = sorted(set(labels) & set(verdicts))
    agree = [case_id for case_id in shared if labels[case_id] == verdicts[case_id]]
    disagree = [case_id for case_id in shared if labels[case_id] != verdicts[case_id]]
    # A judge that says PASS to everything scores well when most cases pass, so
    # report the two error directions separately rather than one blended number.
    judge_lenient = [c for c in disagree if verdicts[c] == "PASS" and labels[c] == "FAIL"]
    judge_strict = [c for c in disagree if verdicts[c] == "FAIL" and labels[c] == "PASS"]
    return {
        "n": len(shared),
        "agreement": len(agree) / len(shared) if shared else 0.0,
        "agree": agree,
        "disagree": disagree,
        "judge_too_lenient": judge_lenient,
        "judge_too_strict": judge_strict,
        "human_only": sorted(set(labels) - set(verdicts)),
        "judge_only": sorted(set(verdicts) - set(labels)),
    }


def main() -> None:
    """Print agreement between the committed labels and one judge run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="judge version to score, e.g. v1 or v2")
    args = parser.parse_args()

    verdict_file = Path(__file__).parent / f"judge_verdicts_{args.version}.json"
    if not verdict_file.exists():
        raise SystemExit(f"{verdict_file.name} not found - run run_judge.py {args.version} first")
    stored = json.loads(verdict_file.read_text(encoding="utf-8"))
    verdicts = {case_id: str(v).upper() for case_id, v in stored["verdicts"].items()}
    reasons = stored.get("reasons", {})

    labels = load_labels()
    result = score(labels, verdicts)

    print(f"judge {args.version} vs human labels on {result['n']} case(s)")
    print(f"agreement: {result['agreement']:.0%} ({len(result['agree'])}/{result['n']})")
    print(f"  judge too lenient (human FAIL, judge PASS): {len(result['judge_too_lenient'])}")
    print(f"  judge too strict   (human PASS, judge FAIL): {len(result['judge_too_strict'])}")
    if result["human_only"]:
        print(f"  labelled but not judged: {', '.join(result['human_only'])}")
    if result["judge_only"]:
        print(f"  judged but not labelled: {', '.join(result['judge_only'])}")

    if result["disagree"]:
        print("\ndisagreements")
        for case_id in result["disagree"]:
            print(f"  {case_id}: human={labels[case_id]}  judge={verdicts[case_id]}")
            print(f"    judge said: {reasons.get(case_id, '(no reason captured)')}")

    history = {}
    if AGREEMENT_FILE.exists():
        history = json.loads(AGREEMENT_FILE.read_text(encoding="utf-8"))
    history[args.version] = {key: result[key] for key in ("n", "agreement", "disagree")}
    AGREEMENT_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"\nwrote {AGREEMENT_FILE.name} ({', '.join(sorted(history))})")


if __name__ == "__main__":
    main()
