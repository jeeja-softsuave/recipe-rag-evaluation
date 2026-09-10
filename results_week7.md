# Week 7 — racing the recipe agent against a fixed workflow

## The eight numbers, same 10 requests, same tools, same model

| | agent | workflow | ratio |
|---|---|---|---|
| pass rate | **100%** (10/10) | 60% (6/10) | — |
| p50 latency | 68.54s | **6.76s** | 10.1× slower |
| total tokens | 34,666 | **1,535** | 22.6× more |
| cost per request | $0.001485 | **$0.000102** | 14.5× more |
| model calls | 35 | 10 | 3.5× more |

Model: `gemini-3.6-flash` for both. Tools identical and deterministic. Output contract
identical and composed in code from the tool transcript on both sides. Per-run detail in
`race.csv`, raw runs in `race_results.json`.

## Pass rate by request class — where the race is actually decided

| class | n | agent | workflow |
|---|---|---|---|
| simple | 6 | 6/6 | **6/6** |
| cascade | 3 | **3/3** | 0/3 |
| unsatisfiable | 1 | **1/1** | 0/1 |

The workflow's four failures all name the same defect — one swap, never re-checked:

```
q07 (cascade)       substitutions=[('thick sour curd', 'coconut milk yoghurt')]
q08 (cascade)       substitutions=[('grated coconut', 'ground cashew paste')]
q09 (cascade)       substitutions=[('thick sour curd', 'coconut milk yoghurt')]
q10 (unsatisfiable) no_safe_substitute=False
```

On q07 it stopped at coconut milk yoghurt while the user was also avoiding coconut. The
agent continued to soy yoghurt. That is the whole difference between the two systems.

## The third tool

`substitute_ingredient(ingredient, avoid)` — added in `tools.py`. One job: replace exactly
one ingredient for exactly one constraint, and report which allergens the replacement itself
contains. `avoid` is an enum of seven values, so the model cannot invent a constraint the
table has never heard of.

Description non-overlap is enforced by a rule applied to all three tools: state the one job,
then disclaim the other two tools' jobs.

- `search_recipes` — "Search only. Does not scale quantities and does not substitute or check ingredients for allergens."
- `scale_recipe` — "Arithmetic only. Requires a recipe_id obtained from search_recipes. Does not find recipes and does not substitute or check ingredients."
- `substitute_ingredient` — "One ingredient and one constraint per call; call it again if the replacement violates another constraint. Does not find recipes and does not scale quantities."

The `substitute_contains` field is what makes a cascade discoverable at all: without it the
agent has no way to learn that its own fix broke a second constraint.

## Budgets — all four enforced, two real terminations

`agent.py` checks every budget on every lap before spending another call:
`MAX_ITERATIONS=8`, `MAX_TOKENS=20000`, `MAX_COST_USD=0.02`, `MAX_WALL_CLOCK_SECONDS=90`.

`test_budgets.py` drives all four with a stubbed model, so enforcement is proven with zero
API calls — 15 checks, including that per-lap tokens are summed rather than only the final
call being counted (420, not 140, over three laps).

Termination 1 — deliberate demo, `budget_demo.log`:

```
STOP budget:max_iterations after 2 laps (limit 2)
stop_reason : budget:max_iterations
```

Termination 2 — unplanned, inside the race itself, on q10:

```
lap 3: substitute_ingredient({"avoid":"yeast","ingredient":"slurry of 3g dry yeast in warm water"}) -> substituted: false
STOP budget:wall_clock at 111.1s (limit 90.0s)
```

Both stopped cleanly instead of spinning, and in the q10 case the contract was already
correct when the budget fired, so a breached budget still returned a usable answer.

## Prediction versus outcome

`race_prediction.txt` was committed before the race ran, off a zero-call dry run that stubbed
the workflow's single model call with a perfect parse.

| | predicted | actual |
|---|---|---|
| workflow pass rate | ≤6/10, "most likely 5 or 6" | **6/10** |
| agent pass rate | 8–10/10 | **10/10** |
| token ratio | 20–30× | **22.6×** |
| latency ratio | ~5× | 10.1× |

The pass rates landed as predicted. The latency ratio was worse than predicted, for a reason
worth naming rather than hiding — see caveats.

## Operational finding: rate limit, not tokens, is the binding constraint

The agent averages 3.5 model calls per request against a free-tier allowance of 20 requests
per day per project. That caps the agent at **five requests a day**; the workflow, at one
call each, serves twenty. Completing this race took three separate Google Cloud projects.

Cost per request understates this. An agent does not merely spend more, it spends in bursts
against a per-project ceiling, and that ceiling is what actually stopped work.

## Caveats, stated rather than left to be found

1. **`substitutions.json` is curated for this exercise, not extracted from the six recipe
   cards.** The corpus states exactly one substitution (sanna palm toddy → a 3g dry yeast
   slurry, marked `source: "corpus"`); the other seven rows are hand-written so that
   cascades exist. Without them there is no cascade class and the workflow wins by
   construction — the brief's first common mistake.
2. **The agent's runs spanned three projects; the workflow's ran entirely on one.** Latency
   on the later projects was markedly higher (q04 102s, q09 118s, q10 111s, against 21–38s
   on the first). The 10.1× latency ratio therefore carries project noise, and it is what
   pushed q10 over the 90s wall-clock budget. Token, call and cost figures are unaffected.
3. **Cost is modelled, not billed.** The free tier bills nothing, so cost is derived from
   token counts at a stated list-price assumption in `agent.py`
   (`PRICE_INPUT_PER_1M_USD`, `PRICE_OUTPUT_PER_1M_USD`). Replace with a real rate to get
   real money.
4. **There was no pre-existing agent.** The brief describes adding a third tool to an
   existing loop; this repo had a RAG pipeline and no loop, so `search_recipes` and
   `scale_recipe` were written in the same change as `substitute_ingredient`.
5. **The output contract is composed in code on both sides.** The agent first attempted to
   emit the contract itself and answered in prose markdown despite an explicit instruction,
   solving the cascade correctly but failing the contract. Rather than force a schema, both
   systems now build the contract from tool results — symmetric, and it measures tool-use
   decisions instead of formatting compliance.

## Reproduce

```
python test_budgets.py                       # all four budgets, zero API calls
python workflow.py "moru for 16 glasses, dairy free"
python agent.py "moru for 16 glasses, dairy free and coconut free"
python race.py --system both --pace 20       # resumable
python race.py --report                      # the eight numbers, no calls
```
