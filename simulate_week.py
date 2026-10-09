"""Replay a week of production traffic through the instrumented app into logs/app.jsonl.

Every answer is a real model call made today; only the clock is simulated. The plan -
which user asks what, when, under which prompt version - is fixed by a seed and written
to logs/traffic_plan.json before any call, so a resumed run continues the same week.

The week is Mon 2026-09-28 to Sun 2026-10-04. Prompt v1 serves until the v2 rollout at
10:00 IST on Wed 2026-09-30 (04:30 UTC); v2 serves from then on.

    python simulate_week.py --key 2          # resumable; stops when a key's quota is spent
"""

from __future__ import annotations

import argparse
import json
import os
import random
from datetime import datetime, timedelta, timezone

from observe import LOG_DIR, answer_observed, append_log, collection, load_log
from recipe_rag import is_rate_limit_error

PLAN_FILE = LOG_DIR / "traffic_plan.json"
SEED = 20260928
WEEK_START = datetime(2026, 9, 28, tzinfo=timezone.utc)
ROLLOUT_V2 = datetime(2026, 9, 30, 4, 30, tzinfo=timezone.utc)
DAY_OPEN_UTC_HOURS = (2.5, 16.5)  # 08:00 to 22:00 IST
USERS = ["u-anitha", "u-bala", "u-chitra", "u-deepak", "u-ezhil", "u-farida", "u-gopal", "u-hema"]
QUESTIONS = [
    "how long do i soak the rice for idli",
    "how much salt goes in idli batter",
    "can i make kallappam without yeast",
    "what can i use instead of coconut in kallappam",
    "is neeragaram safe to drink after two days",
    "my kid is allergic to coconut, can she have sanna",
    "dairy free swap for the curd in moru",
    "how many paniyarams does the batter make",
    "what temperature should idli batter ferment at",
    "vegan option for moru",
    "can i use brown rice instead of idli rice",
    "how much toddy goes in sanna",
    "is kuzhi paniyaram gluten free",
    "what replaces fenugreek in idli batter",
    "how do i know if neeragaram has gone bad",
    "milk allergy, is idli ok",
    "can i swap the shallots in moru for onion",
    "double the moru recipe, how much curd",
    "can i use store bought yoghurt for moru",
    "calories in a glass of moru",
    "nut free version of kallappam",
    "what can i use instead of urad dal for a lighter idli",
    "lactose intolerant, which of these ferments can i have",
    "can i ferment idli batter in the fridge",
]


def build_plan() -> list[dict[str, str]]:
    """One request per question, at a seeded time and user, in time order."""
    rng = random.Random(SEED)
    plan = []
    for question in QUESTIONS:
        day = rng.randrange(7)
        hours = rng.uniform(*DAY_OPEN_UTC_HOURS)
        at = WEEK_START + timedelta(days=day, hours=hours)
        plan.append({"at": at.isoformat(timespec="seconds"), "user_id": rng.choice(USERS),
                     "question": question,
                     "prompt_version": "v2" if at >= ROLLOUT_V2 else "v1"})
    plan.sort(key=lambda item: item["at"])
    return [{"seq": number, **item} for number, item in enumerate(plan, start=1)]


def main() -> None:
    """Write the plan once, then answer every planned request not yet in the log."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", type=int, default=1, help="which GEMINI_API_KEY slot to use")
    args = parser.parse_args()
    name = "GEMINI_API_KEY" if args.key == 1 else f"GEMINI_API_KEY{args.key}"
    os.environ["GEMINI_API_KEY"] = os.environ[name]

    LOG_DIR.mkdir(exist_ok=True)
    if not PLAN_FILE.exists():
        PLAN_FILE.write_text(json.dumps(build_plan(), indent=2) + "\n", encoding="utf-8")
    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    done = {(line["timestamp"], line["user_id"], line["question"]) for line in load_log()}
    index = collection()
    for item in plan:
        if (item["at"], item["user_id"], item["question"]) in done:
            continue
        try:
            record = answer_observed(item["question"], item["user_id"], item["prompt_version"],
                                     index=index, at=item["at"])
        except Exception as error:
            if is_rate_limit_error(error):
                print(f"quota spent on key {args.key} at seq {item['seq']}; rerun with another key")
                return
            raise
        append_log(record)
        print(f"{item['seq']:>2} {item['at']} {item['prompt_version']} {item['user_id']:<9} "
              f"{record['input_type']:<12} {record['cost_usd']:.6f} {item['question']}")
    print(f"week complete: {len(load_log())} lines in logs/app.jsonl")


if __name__ == "__main__":
    main()
