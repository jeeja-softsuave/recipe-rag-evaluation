# Week 11: find the dairy-free swap that wasn't, and close the loop

## What I built (the "Week 11 app" did not exist yet)

| File | Job |
|---|---|
| `observe.py` | the RAG app, instrumented: one JSON log line per request, with user, input type, prompt version, model, context ids and scores, and per-span latency, tokens and cost (retrieval, generation, tools), plus `swap_flags` (bonus) |
| `prompts.py`, `prompt_release.json` | versioned prompts and the release switch (production + hash-bucket canary) |
| `simulate_week.py` | a seeded week of traffic (Mon 2026-09-28 to Sun 2026-10-04), v1 → v2 rollout on Wednesday. Real model calls, simulated clock. |
| `plant.py` | sealed planter: one bad swap answer, chosen from OS randomness, never printed |
| `logq.py` | the on-call query tool: one filter per slice (time, user, prompt version, input type, cost outlier), plus an output regex and `--unsafe-swap` |
| `run_suite.py` | regenerates the whole suite through the app at a given prompt version; scores it with every assertion and `judge_v2` |

## The first finding: the complaint does not reproduce as worded

Before building anything, 12 probe calls checked whether the app can produce the complaint at all.
- **Prompt v1** (strict) refused every dairy swap question, 5 of 6. It never recommends a swap.
- **Prompt v2** (helpful) suggested only genuinely dairy-free swaps (soy or coconut yoghurt),
  **but never named soy or coconut as allergens.**

The planted "lactose-free curd is dairy-free" answer is therefore synthetic, as the brief
intends. The real failure underneath it is v2's unwarned plant swaps, and that is what the
eval case catches.

## Results

| Requirement | Result | File |
|---|---|---|
| 1. Time-to-find | **00:10**; slice: time + output text. Bonus round: **00:08** with `swap_flags`. | `drill.md` |
| 2. The trace | `t-e79ea9256d`: v2, per-span latency/tokens/cost, 5 context ids | `trace.json` |
| 3. RED → GREEN | full suite with judge: **25/36 on v2** (w11-01 FAIL) → **33/36 on v4** (w11-01 PASS); assertions alone 26/36 → 36/36. Fix attempt v3 scored 26/36 with the judge and was not shipped. | `suite_red_green.md`, `eval_cases_week11.jsonl` |
| 4. Version bump + canary | **v2 → v4** at a 10% canary; rollback = one config line | `prompt_release.json`, `canary_plan.md` |
| 5. Cost by stage + 10× | generation is **100%** of cost ($0.000261/query); at 10×, **the 20 RPD rate limit breaks first** (60/day needed) | `cost_by_stage.md`, `tenx.md` |

## What the loop caught that a single test would not

1. **v3, my first fix, made things worse in two places.** s07 and r09 passed on v2 and
   failed on v3, and w11-02 went red too. Only the full rerun showed it. Without the rerun,
   v3 would have shipped two new failures to fix one.
2. **v3 leaked its own prompt.** It listed forbidden products ("lactose-free milk or curd,
   ghee, ...") and the model echoed that sentence into an answer, which the dairy check
   then caught. v4 names no forbidden products and frames rules as rules.
3. **v2 broke citations it did not need to break.** Its `[general]` tag is a bracket that
   is not a chunk id, so `cited_chunks_exist` failed on 5 cases. v4 labels general advice
   in words.
4. **v4 also fixed 4 cases that were already failing on v1:** r02, s17, r06, r08. These were
   format failures (lists in one bracket, a sentinel inside prose, a dairy recipe with no
   dairy warning) that v4's explicit rules cover.

## Caveats, stated rather than found later

- **The drill is partly memory.** I wrote the planter, so I knew its wording. A colleague
  planting free text is the real test. The bonus field exists precisely so the find does
  not depend on wording.
- **The suite ran on `gemini-3.5-flash-lite`, not production's `gemini-3.6-flash`,** because
  the 3.6 Flash free quota (an account-level cap, as the AI Studio usage page showed) was
  spent. All four versions ran on the same model, so the comparison holds, but on a
  smaller model.
- **The judge ran on `gemini-3.5-flash-lite`, not Week 6's `gemini-3.6-flash`.** The
  `judge_v2` prompt is unchanged, but 3.6 Flash was still refused on 2026-10-09. All four
  versions had the same judge, so they compare with each other, not with Week 6's numbers.
- **My prediction about the judge was wrong.** I expected it to fail v4's general-advice
  swaps as ungrounded. It passed them (w11-01, s12, s14: "correctly states the recipe card
  records no substitute"), while it failed v2's `[general]`-tagged versions of the same
  advice on 5 cases. Saying "the card records none" before labelled advice changed the
  judge's verdict, not just the assertions.
- **With the judge, v4 is 33/36, not 36/36.** The 3 remaining failures (s18 on every
  version; r06 and r09 flipping between versions) are pre-existing judge and refusal issues,
  not v4 regressions. They are listed in `suite_red_green.md` as follow-ups.
- **n = 1 per case per version.** w11-02 passed on v2 by refusing; the model is not
  deterministic.
- **The traffic week has 21 real requests of the 24 planned.** The last 3 ran out of quota.
- **Cost is modelled at list prices** from reported tokens; the free tier bills nothing.
