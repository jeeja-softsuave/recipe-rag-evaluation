# Week 8 — the outcome-vs-trajectory gap, and closing one mode

## Headline

The mitigation fixed the answer and did **not** fix the path. Before it, q10 failed both
evals, so outcome and trajectory agreed and the gap was 0%. After it, q10 returns the
correct answer down a route that is still wrong — outcome 100%, trajectory 90%, **gap 10%**.
That is the brief's premise reproduced exactly: a right answer with a passing test and a
wrong path underneath.

## The four trajectory numbers

| | before | after |
|---|---|---|
| tool-choice accuracy | 90% | 90% |
| argument validity rate | 100% | 100% |
| step efficiency (mean / worst) | 1.02 / 1.20 | 1.02 / 1.20 |
| cost per request p50 | $0.001727 | $0.001409 |
| cost per request **max** | $0.003078 | $0.003161 |
| outcome pass rate | 90% | **100%** |
| trajectory pass rate | 90% | 90% |
| **gap** | **0%** | **10%** |

Cost is reported p50 and max because the mean hides the tail: the max run costs 2.2x the
median, and the tail is what lands on a bill.

Agent: `gemini-3.6-flash`, self-reporting via a `submit_answer` tool. 10 cases, same set as
the Week 7 race. Raw runs in `trajectory_runs.json` and `trajectory_runs_after.json`;
scored reports in `trajectory_before.json` and `trajectory_after.json`.

## Requirement 1 — expected sequences, alternate paths as sets

`accepted_paths()` in `trajectory_eval.py` generates every correct ordering from rules
rather than hard-coding one sequence:

- `search_recipes` first, because nothing else runs without a recipe_id.
- One `substitute_ingredient` per constraint, in dependency order - each swap is chosen from
  the previous swap's result.
- `scale_recipe` anywhere after search. **Scaling before or after substituting are both
  correct**, so every position is accepted.
- `submit_answer` last.

Cases with more than one accepted path: q03, q04, q05 (2 each), q07, q08, q10 (3 each),
q09 (4). Only q01, q02 and q06 have a single path, because with no constraint there is
nothing to reorder.

This was not theoretical. Across the two runs the agent used **both** orderings on the same
case - q03 and q04 substituted before scaling in the before run and after scaling in the
after run; q07 and q08 swapped orderings between runs. A single-sequence assertion would
have scored four correct runs as failures and inflated the gap.

## Requirement 3 — the gap, and the right-answer-wrong-path case

**Gap = outcome 100% - trajectory 90% = 10%**, after the mitigation.

The case is **q10**, "sanna for 16, alcohol free and yeast free".

Accepted shortest path (4 tool calls plus submit):

```
search_recipes -> scale_recipe -> substitute_ingredient -> substitute_ingredient -> submit_answer
```

What it actually did:

```
lap 1  search_recipes({"dish": "sanna"})
lap 2  substitute_ingredient({"ingredient": "Toddy, or yeast slurry", "avoid": "alcohol"})
         -> CONFIRMED: slurry of 3g dry yeast in warm water
lap 3  substitute_ingredient({"ingredient": "slurry of 3g dry yeast in warm water", "avoid": "yeast"})
         -> nothing. Correct probe: the replacement itself dead-ends.
lap 4  substitute_ingredient({"ingredient": "Toddy, or yeast slurry", "avoid": "yeast"})
         -> nothing. REDUNDANT: the toddy was already replaced at lap 2; no answer here
            can change the outcome.
lap 5  scale_recipe({"recipe_id": "sanna-03", "target_servings": 16})
lap 6  submit_answer(substitutions=[["Toddy, or yeast slurry", "slurry of 3g dry yeast in warm water"]],
                     no_safe_substitute=true)
```

The submitted answer is exactly right and passes the outcome eval. The path takes **6 steps
where 5 suffice** (efficiency 1.20) and matches no accepted sequence, because it spends a
third `substitute_ingredient` re-probing an ingredient it had already replaced. An outcome
eval alone reports this run as a clean pass.

## Requirement 4 — exactly one mitigation, with the price

**Top mode before: `D_dropped_confirmed_swap`, count 1 (q10).** On the before run the agent
confirmed `Toddy -> yeast slurry` at lap 2, then submitted `substitutions: []` because a
later constraint dead-ended. It threw away a swap the tool had already confirmed, and
`G_outcome_failure` followed directly from it.

**The one change**, to the `submit_answer` description only:

```
  "Submit the final adapted recipe and finish. Call this exactly once, as the last
   step. Records an answer only; does not find recipes, scale quantities or check
   substitutions.
+  List in substitutions EVERY swap a tool already confirmed, in
+  order, even when a later constraint could not be satisfied - in that case also
+  set no_safe_substitute to true, in addition to listing the confirmed swaps,
+  never instead of them."
```

No argument validation, no step limit, no re-planning, no swapping in the workflow.
Shipping two would have made the before -> after unattributable.

**Result: D goes 1 -> 0.** q10 now submits the confirmed swap *and* the dead-end flag, and
`G_outcome_failure` follows it to 0. Outcome pass rate 90% -> 100%.

**The price.** The deterministic part is exact: the description grew from 172 to 413
characters, +241 characters (~60 tokens) added to the tool schema on **every** model call,
which is 3 to 6 calls per request.

The end-to-end measurement is honest but noisy. Over the 7 cases where the lap count did not
change, the token delta averaged **+59 per request**, with a spread of -297 to +340. The
spread is wider than the effect, so at n=10 the per-request token price is **not cleanly
separable from run-to-run variation** in how much the model writes.

What I will not claim: the headline totals show tokens falling 52,396 -> 52,029 and cost p50
falling $0.001727 -> $0.001409. That is **not a saving created by the mitigation**. It comes
from q03 and q04 happening to finish in one fewer lap. Reporting it as a benefit would be
the "calling the mitigation free" mistake with the sign flipped. Cost **max** rose,
$0.003078 -> $0.003161, which is the direction the added schema predicts.

## Requirement 5 — per-mode regression check

| mode | before | after | change |
|---|---|---|---|
| A_wrong_tool_choice | 1 (q10) | 1 (q10) | unchanged |
| B_invented_arguments | 0 | 0 | unchanged |
| C_redundant_steps | 1 (q10) | 1 (q10) | unchanged |
| D_dropped_confirmed_swap | **1 (q10)** | **0** | **closed** |
| E_ungrounded_submission | 0 | 0 | unchanged |
| F_budget_termination | 0 | 0 | unchanged |
| G_outcome_failure | 1 (q10) | 0 | closed, follows D |

**No mode got worse and no new mode appeared.** All seven were checked, and the list above
is the complete taxonomy the eval scores.

The honest reading: the mitigation closed the mode it targeted and the failure that depended
on it, and left A and C exactly where they were. The redundant probe at lap 4 is untouched -
a description telling the model what to *submit* was never going to change which tools it
*calls*. Closing C would need a different lever, which is a second mitigation and therefore
a separate experiment.

## What the gap number really means here

Before the mitigation the gap was 0%, and that was not a good sign - it meant q10 failed
both evals, so the outcome eval happened to catch the one broken case. After the mitigation
the outcome eval is clean at 100% and the trajectory eval still says 90%. The project got
better and the gap got wider, because fixing the answer removed the outcome eval's ability
to see the remaining defect.

That is the argument for trajectory evals in one number: **the better your outcome eval
looks, the more the gap is the only thing still telling you the truth.**

## Caveats

1. **No shortcut was observed.** The brief's premise is an agent that produces a correct
   substitution without calling the allergen tool. Measured across both configurations - the
   Week 7 agent, whose contract is composed in code and structurally cannot shortcut, and
   this self-reporting agent, which can - the agent called `substitute_ingredient` on every
   case that needed one. `E_ungrounded_submission` is 0 in both runs. The mechanism that
   would detect a shortcut is proven by a stubbed test in which an agent submits a correct
   swap it never looked up; the real agent simply did not do it.
2. **One grounding check produced a false positive before it was corrected.** Reading the
   stored logs suggested q03 submitted a swap no tool returned. The logs truncate results at
   120 characters, so the field was cut off. Replaying the deterministic tools locally showed
   zero ungrounded submissions. `tool_returned_swaps()` now replays rather than reads text.
3. **Latency is not compared.** The runs spanned two Google Cloud projects with visibly
   different response times, and at 20 requests per day per project there was no way to hold
   that constant. Token, call and cost figures are unaffected.
4. **n = 10.** Every count in the mode table is a single case. D 1 -> 0 is one run changing
   behaviour, not a rate.

## Reproduce

```
python run_trajectory.py --out trajectory_runs.json           # self-reporting agent, 10 cases
python trajectory_eval.py --results trajectory_runs.json --label before --out trajectory_before.json
python trajectory_eval.py --results trajectory_runs_after.json --label after --out trajectory_after.json
```
