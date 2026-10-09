# Week 11 drill: find the dairy-free swap that wasn't

**Complaint received:** "someone said it recommended a dairy-free substitution that wasn't
dairy-free, sometime last week." No trace id, no timestamp, no recipe name.

## Result

| | |
|---|---|
| Time-to-find | **00:10** (clock start 13:16:22 UTC, stop 13:16:32 UTC, 2026-10-08) |
| Slice that found it | **time** (last week, 2026-09-28 to 2026-10-05), plus a **regex over the output text** |
| Found | `t-e79ea9256d`, 2026-09-30 13:56:02 UTC, user `u-gopal`, prompt **v2**, input type `substitution` |
| What it said | "...For a dairy-free version, use **lactose-free curd** instead; lactose-free curd is dairy-free..." Lactose-free curd is still dairy. |
| Planted by | `plant.py`, a sealed script, run 2026-10-08 13:15 UTC. **Not a named squadmate**; see the honesty notes below. |

## What I ran

```
$ python logq.py --since 2026-09-28 --until 2026-10-05 --grep "dairy.?free|non.?dairy" --in output
  2 of 22 requests
  t-e79ea9256d  u-gopal  v2 substitution  A: ...use lactose-free curd instead; lactose-free curd is dairy-free...
  t-eb2293602a  u-bala   v2 substitution  A: ...dairy-free yogurt (such as coconut or soy yogurt)...
$ python logq.py --trace t-e79ea9256d          -> trace.json
```

**Why the output, not the input.** The complaint describes what the app *said* ("recommended
... dairy-free"), not what the user asked. A search over questions alone would have
missed it: the planted question says "without dairy", not "dairy-free". This is the brief's
common mistake #3.

**The second hit is not the complaint, but it is not clean either.** `t-eb2293602a` is a
real v2 answer. Its swap (coconut or soy yoghurt) really is dairy-free, but it gives no
warning that coconut and soy are allergens themselves. The eval case covers both failures.

## The other slices, and why they would not have found it

| Slice | Result on this log |
|---|---|
| Time alone | 22 requests last week: a full read, not a find |
| User | The complaint names no user |
| Prompt version | `--prompt v2` narrows to 15 requests: helpful, but not decisive. It does point at the root cause: v2 is the version that is allowed to suggest swaps. |
| Input type | `--type substitution` narrows to 9 requests; the bad one is among them |
| Cost outlier | 2 requests over mean + 2 sd (`t-4d395297ab`, `t-6aac169000`): both are long, correct allergen answers. The bad one is not among them. It cost $0.000261, almost exactly the log mean of $0.000261, which is realistic: a wrong answer costs the same as a right one. |

## Two log findings on the way

1. **`citations_ok` is noise under v2.** It is `false` on 9 lines: 8 of them are v2 answers
   tagged `[general]`, which the citation checker reads as a missing chunk id. A field
   that fires on every helpful answer cannot single out the harmful one.
2. **The plant is detectable forensically.** Its generation span latency (58,004.2 ms) is
   identical to the real line `t-9cb2486400`'s, because the planter copied it. Duplicate
   span timings are how a forged log line would be spotted.

   Separately, two real v2 requests took **53–58 s** in generation, against a minimum of
   5.4 s. That is rate-limit retry time counted inside the span: a latency outlier that no
   cost slice can see.

## Honesty notes (these qualify the 00:10)

- **This is memory, not only tooling.** I wrote `plant.py`, so I knew the pool of bad answers
  (all use the phrase "dairy-free version") before the clock started. That is the brief's
  common mistake #6. A colleague planting free text could have written "vegan", "milk-free"
  or "safe for a milk allergy" instead, and my regex would have missed every one.
- **What the tool really contributes** is an output index plus a time window. **What it
  lacks** is a structured field for *what the answer recommended*. That is the field the
  bonus adds.
- **The missing log field:** `swap_claims`, recorded at log time: each substitute the answer
  recommends, plus its allergen flags. With it, the query becomes "a swap claimed for a
  dairy-free request that carries a dairy flag", which is independent of wording. Without
  it, the find depends on guessing the words the bad answer used.

---

## Bonus: the field that closed the gap, and a second drill

**The field added:** `swap_flags`, written on every log line by `observe.py`, with the same
rules as the suite's `dairy_free_swap_is_safe`:

```json
"swap_flags": {"dairy_free_request": true, "dairy_products_named": ["goat's milk"], "plant_swaps_unwarned": []}
```

`reindex_logs.py` backfilled it onto all 22 existing lines from their stored question and
answer, with no model calls. `logq.py --unsafe-swap` queries it.

**Second plant:** `plant.py --round 2`, sealed like round 1, but its answers never say
"dairy-free" or "non-dairy". They say things like "safe for a milk allergy", which is
exactly what round 1's regex depended on.

| | Round 1 | Round 2 |
|---|---|---|
| Time-to-find | 00:10 | **00:08** (16:07:49 → 16:07:57 UTC) |
| Query | `--grep "dairy.?free\|non.?dairy" --in output` | `--unsafe-swap` |
| Found | `t-e79ea9256d` (lactose-free curd) | `t-0c8d75c280` ("goat's milk curd is fine for anyone allergic to cow's milk") |
| Would round 1's query find round 2's line? | — | **No**: rerun after the find, it returns only `t-e79ea9256d` and `t-eb2293602a` |

**What actually closed the gap is not the 2 seconds.** Round 1 was fast because I knew the
wording. Round 2 is fast whatever the wording. The structured field turns "guess the words the
bad answer used" into "ask what the answer recommended".

**It also found something the regex never did:** `t-a9ec13ca3f`, a **real** v2 answer to
"vegan option for moru" that recommends soy or coconut yogurt and names neither as an
allergen. It never says "dairy-free", so round 1's search could not see it. That makes three
real or planted unsafe swaps visible in one query, against two.

**Same honesty limit as round 1:** I wrote both the planter's pools and the field's patterns.
"Goat's milk" is in `DAIRY_PRODUCT_PATTERN` because I put it there. Checked: the pattern
**misses "camel milk", "buffalo curd" and "sheep yoghurt"**, all dairy. A pattern list
never generalises on its own; the durable fix is to flag any recommended ingredient by looking
it up in the ingredient database's dairy flag, not by matching a list of words.
