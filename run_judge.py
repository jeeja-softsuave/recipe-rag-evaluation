"""Run one judge prompt version over the substitution outputs, in batches.

Refuses to call the API until labels_25.json is filled and committed, because the
whole point of the exercise is that the human labels predate the judge's verdicts.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import chromadb

from make_labels import LABELS_FILE, PLACEHOLDER, chunk_texts
from recipe_rag import CHROMA_DIR, GEMINI_MODEL, STRUCTURE_AWARE_COLLECTION, _gemini_generate
from run_substitutions import load_outputs

PROMPT_MARKER = "--- PROMPT SENT TO THE MODEL BELOW THIS LINE ---"
BATCH_SIZE = 10
# A local 8B model follows a single-case instruction far more reliably than a batch,
# and with no quota there is no reason to batch at all.
OLLAMA_BATCH_SIZE = 1
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_TIMEOUT_SECONDS = 300
VERDICT_PATTERN = re.compile(
    r"^\s*CASE\s+(\S+?)\s*:\s*(PASS|FAIL)\b\s*[-—:]*\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def ollama_generate(system_prompt: str, user_prompt: str) -> str:
    """Send one judging request to a locally running Ollama server."""
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            # Deterministic so a rerun of the same case gives the same verdict.
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise SystemExit(
            f"cannot reach Ollama at {OLLAMA_URL} ({error}). "
            "Start it with:  ollama serve      and pull the model:  ollama pull " + OLLAMA_MODEL
        ) from error
    return body["message"]["content"]


def judge_prompt(version: str) -> str:
    """Return only the part of the judge file that is actually sent to the model."""
    path = Path(__file__).parent / f"judge_{version}.txt"
    text = path.read_text(encoding="utf-8")
    if PROMPT_MARKER not in text:
        raise SystemExit(f"{path.name} has no '{PROMPT_MARKER}' line")
    return text.split(PROMPT_MARKER, 1)[1].strip()


def check_labels_committed() -> None:
    """Stop before spending a call if the labels are not yet locked into git history."""
    if not LABELS_FILE.exists():
        raise SystemExit(f"{LABELS_FILE.name} does not exist - label the cases first")
    stored = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    unfilled = [case_id for case_id, v in stored["labels"].items() if v == PLACEHOLDER]
    if unfilled:
        raise SystemExit(f"{len(unfilled)} label(s) still unfilled: {', '.join(unfilled)}")
    committed = subprocess.run(
        ["git", "log", "--oneline", "--", LABELS_FILE.name],
        capture_output=True,
        text=True,
        cwd=LABELS_FILE.parent,
    ).stdout.strip()
    if not committed:
        raise SystemExit(
            f"{LABELS_FILE.name} is filled but NOT COMMITTED.\n"
            "Commit it before running the judge - the judge running first destroys the\n"
            "ordering evidence that the labels were written blind."
        )
    dirty = subprocess.run(
        ["git", "diff", "HEAD", "--name-only", "--", LABELS_FILE.name],
        capture_output=True,
        text=True,
        cwd=LABELS_FILE.parent,
    ).stdout.strip()
    if dirty:
        raise SystemExit(f"{LABELS_FILE.name} has uncommitted edits - commit them first")
    print(f"labels committed as: {committed.splitlines()[0]}")


def render_case(output: dict[str, Any], texts: dict[str, str]) -> str:
    """Render one case for the judge: the question, the answer, and the context it saw."""
    lines = [
        f"CASE {output['case_id']}",
        f"QUESTION: {output['request']}",
        f"ANSWER: {output['answer'].strip()}",
        "CONTEXT:",
    ]
    for chunk in output["retrieved"]:
        body = " ".join(texts.get(chunk["chunk_id"], "").split())
        lines.append(f"  [{chunk['chunk_id']}] {body}")
    return "\n".join(lines)


def parse_verdicts(raw: str) -> dict[str, dict[str, str]]:
    """Pull one verdict per CASE line out of the judge's reply."""
    parsed: dict[str, dict[str, str]] = {}
    for case_id, verdict, reason in VERDICT_PATTERN.findall(raw):
        parsed[case_id.strip()] = {
            "verdict": verdict.upper(),
            "reason": reason.strip(),
        }
    return parsed


def main() -> None:
    """Judge every generated case with one prompt version and store the verdicts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="judge prompt version, e.g. v1 or v2")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the assembled prompt and make no API call",
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "ollama"],
        default="gemini",
        help="which model judges; ollama runs locally and costs no quota",
    )
    args = parser.parse_args()

    system_prompt = judge_prompt(args.version)
    outputs = load_outputs()
    case_ids = sorted(outputs)
    collection = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(
        STRUCTURE_AWARE_COLLECTION
    )

    size = OLLAMA_BATCH_SIZE if args.provider == "ollama" else BATCH_SIZE
    generate = ollama_generate if args.provider == "ollama" else _gemini_generate
    model_name = OLLAMA_MODEL if args.provider == "ollama" else GEMINI_MODEL
    batches = [case_ids[i : i + size] for i in range(0, len(case_ids), size)]
    if args.dry_run:
        print(f"judge_{args.version}.txt -> {len(case_ids)} cases in {len(batches)} call(s)\n")
        first = batches[0] if batches else []
        texts = chunk_texts(collection, [c["chunk_id"] for cid in first for c in outputs[cid]["retrieved"]])
        print("=== SYSTEM ===")
        print(system_prompt)
        print("\n=== INPUT (first batch) ===")
        print("\n\n".join(render_case(outputs[cid], texts) for cid in first))
        return

    check_labels_committed()

    verdicts: dict[str, str] = {}
    reasons: dict[str, str] = {}
    raw_batches: list[str] = []
    for number, batch in enumerate(batches, start=1):
        chunk_ids = [c["chunk_id"] for cid in batch for c in outputs[cid]["retrieved"]]
        texts = chunk_texts(collection, chunk_ids)
        user_prompt = "\n\n".join(render_case(outputs[cid], texts) for cid in batch)
        print(f"batch {number}/{len(batches)}: {len(batch)} cases")
        raw = generate(system_prompt, user_prompt)
        raw_batches.append(raw)
        parsed = parse_verdicts(raw)
        for case_id in batch:
            if case_id not in parsed:
                print(f"  WARNING: no verdict line for {case_id}")
                continue
            verdicts[case_id] = parsed[case_id]["verdict"]
            reasons[case_id] = parsed[case_id]["reason"]
        stray = sorted(set(parsed) - set(batch))
        if stray:
            print(f"  WARNING: verdicts for cases not in this batch: {', '.join(stray)}")

    suffix = args.version if args.provider == "gemini" else f"{args.version}_{args.provider}"
    out_file = Path(__file__).parent / f"judge_verdicts_{suffix}.json"
    payload = {
        "judge_version": args.version,
        "provider": args.provider,
        "model": model_name,
        "verdicts": verdicts,
        "reasons": reasons,
        "raw_batches": raw_batches,
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # run_eval.py reads the unversioned name, so keep it pointing at the newest run.
    (Path(__file__).parent / "judge_verdicts.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    passes = sum(1 for v in verdicts.values() if v == "PASS")
    print(f"\n{len(verdicts)} verdicts ({passes} PASS) -> {out_file.name}")


if __name__ == "__main__":
    main()
