"""Backfill swap_flags onto every log line written before the field existed.

The field is derived only from the stored question, answer and refusal, so the backfill
needs no model call and gives old lines exactly what the logger now writes for new ones.
"""

from __future__ import annotations

import json

from observe import APP_LOG, load_log, swap_flags


def main() -> None:
    """Add the field where it is missing; leave every other byte of each line alone."""
    lines = load_log()
    added = 0
    for line in lines:
        if "swap_flags" not in line:
            line["swap_flags"] = swap_flags(line["question"], line["answer"], line["refused"])
            added += 1
    with APP_LOG.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"swap_flags added to {added} of {len(lines)} lines")


if __name__ == "__main__":
    main()
