# Week 5 notes — sample, open coding, replay, prediction

## 1. The seeded sample

**Seed: `20260824`** · `random.Random(20260824).sample(population, 20)` · `sample_traces.py`

**Population: 174 candidate questions**, enumerated from the cards themselves — every template
applied to every ingredient name parsed out of the ingredient tables, plus per-recipe templates
(how do I make, how long, what temperature, yield, dairy allergy, ratio, steam, overnight), plus
out-of-corpus templates (calories, protein, where to buy) and three unrelated questions. Nothing was
hand-picked, so the sample could not be steered toward the two failures already known from Week 4.

**Honest provenance.** The app had never logged a trace, so this population is **synthetic** — a
mechanically enumerated question space, not real user traffic. Frequencies below describe the app's
behaviour across that space. Three real demo questions exist and are reserved for the bonus sample
(the curated demo set), per the requirement that the random 20 not be the demo recipes.

The 20 selected, with the trace each produced:

| candidate | kind | question | trace_id |
|---|---|---|---|
| c117 | out_of_corpus | how many calories in moru | `t-7643654d90` |
| c082 | recipe | what ratio does sanna use | `t-37d6fe47d8` |
| c171 | out_of_corpus | where can i buy ingredients for neeragaram | `t-be30b034af` |
| c009 | ingredient | how many grams of fenugreek seeds in kuzhi paniyaram batter | `t-0bac1bbf8d` |
| c102 | ingredient | how many grams of ginger in moru | `t-ccb889defa` |
| c025 | out_of_corpus | what is the protein content of kuzhi paniyaram batter | `t-7e74d8e174` |
| c116 | recipe | can i leave moru overnight | `t-46e29c4af8` |
| c124 | ingredient | idli batter whole white urad dal quantity | `t-ec598be107` |
| c008 | ingredient | kuzhi paniyaram batter fenugreek seeds quantity | `t-745286a211` |
| c148 | ingredient | how many grams of cooked rice in neeragaram | `t-e1b8a19406` |
| c045 | ingredient | how much active dry yeast for kallappam batter | `t-ce8ae0f182` |
| c111 | recipe | what temperature for moru | `t-187716b1dd` |
| c053 | recipe | what ratio does kallappam batter use | `t-90fb21ce38` |
| c016 | recipe | how do i make kuzhi paniyaram batter | `t-8d580a7ac5` |
| c151 | ingredient | how many grams of water in neeragaram | `t-5c7b2a1d64` |
| c081 | recipe | is sanna safe for a dairy allergy | `t-62532e8648` |
| c120 | ingredient | how much idli rice for idli batter | `t-102aad4611` |
| c048 | recipe | how do i make kallappam batter | `t-f3c0b146f5` |
| c142 | recipe | can i leave idli batter overnight | `t-a3946a1fda` |
| c069 | ingredient | sanna toddy quantity | `t-c1b5435192` |

Note c069 — "sanna toddy quantity" — is the exact question that failed in Week 4. It came up by
chance, not by choice; the seed proves it.

## 2. Open coding — one observation sentence per trace

Written while reading `traces.jsonl`, describing what I saw. **Zero code changes were made during
this step**; the tooling was committed beforehand in `4a3d991` and nothing was touched until the
taxonomy was finished.

1. **`t-7643654d90`** — Retrieved five moru chunks and replied `NOT_IN_CORPUS`; no calorie figure appears anywhere on the moru card.
2. **`t-37d6fe47d8`** — Replied `NOT_IN_CORPUS` although the rank-1 chunk states sanna's hydration as 50% from grinding water plus 24% from the toddy, and a different recipe's "Rice to dal ratio: 3:1" line sat at rank 5.
3. **`t-be30b034af`** — Retrieved five neeragaram chunks and replied `NOT_IN_CORPUS`; the cards contain no purchasing information at all.
4. **`t-0bac1bbf8d`** — Answered "6g of fenugreek seeds" citing the ingredients table, and the citation check confirmed 6g is in that chunk.
5. **`t-ccb889defa`** — Answered "10g of crushed ginger" citing the moru table, matching the card exactly.
6. **`t-7e74d8e174`** — Replied `NOT_IN_CORPUS` to a protein question with five paniyaram chunks in context, none of which mention nutrition.
7. **`t-46e29c4af8`** — Replied `NOT_IN_CORPUS` to "can i leave moru overnight" while the rank-1 chunk said to leave it standing 2 hours at room temperature and to refrigerate before serving.
8. **`t-ec598be107`** — Answered "200g" of urad dal citing the idli table, while a second recipe's table that also lists 200g urad dal sat at rank 3 uncited.
9. **`t-745286a211`** — Answered "6g (which is 1% of the base rice weight)" and both figures were checked against the cited chunk and matched.
10. **`t-e1b8a19406`** — Answered "300 grams of cooked rice", which matches the card, but wrote the unit as the word "grams" and the citation check recorded no claimed values while still reporting ok.
11. **`t-ce8ae0f182`** — Answered "3g (0.6% of the base rice weight)" of yeast, both figures verified against the cited chunk.
12. **`t-187716b1dd`** — Asked for a temperature and answered with a duration — "left to stand at room temperature for 2 hours" — and the citation check recorded no claimed values.
13. **`t-90fb21ce38`** — Replied `NOT_IN_CORPUS` to kallappam's ratio while the rank-1 chunk stated "Hydration: 84%" and another recipe's explicit ratio line sat at rank 3.
14. **`t-8d580a7ac5`** — Produced a seven-step numbered procedure with a citation on every step, all steps matching the card, and all eight citation checks recorded no claimed values including the step that wrote "30°C".
15. **`t-5c7b2a1d64`** — Answered "900g of water" citing the neeragaram table, verified and matching.
16. **`t-62532e8648`** — Answered "Yes, Sanna is safe for a dairy allergy as it is vegan" citing sanna's allergen note, while the rank-1 chunk was moru's allergen note — moru being the only dairy recipe in the corpus.
17. **`t-102aad4611`** — Answered "800g of parboiled idli rice", verified, with another recipe's ingredients table at rank 5.
18. **`t-f3c0b146f5`** — Produced a five-step procedure citing kallappam's method chunks, with a different recipe's method chunk sitting at rank 2 and seven citation checks recording no claimed values.
19. **`t-a3946a1fda`** — Answered "Yes, idli batter is fermented for 10 to 12 hours at 28C" to a question about leaving it overnight, asserting a yes the cited chunk does not state.
20. **`t-c1b5435192`** — Answered "120g of toddy … 24% of the base rice weight", both correct, but placed two chunk ids inside one bracket and the run was recorded as `all_citations_ok=False` having performed zero checks.

I do not know why trace 16 put moru's allergen note above sanna's own for a question naming sanna.

## 3. Replay evidence

**Seed `20260824`**, `random.Random(20260824).choice(traces)` → **`t-c1b5435192`** ("sanna toddy
quantity"). Replayed using only what the trace stored — no index, no retrieval.

Fields the trace carried: `prompt_version=v1`, `model=gemini-3.6-flash`,
`params={thinking_level: low}`, `top_k=5`, all five `chunk_id`s **with scores**, the full
`system_prompt`, the full `user_prompt`, and `raw_output`.

**The prompt rebuilt from the trace's stored chunks matched the stored prompt byte for byte
(`True`)** — so the retrieval half of this trace is fully reconstructable.

```
ORIGINAL : The recipe requires 120g of toddy (or yeast slurry), which is 24% of the base rice
           weight [sanna-03::structure::0, sanna-03::structure::1].
REPLAYED : The recipe uses 120g of toddy (which is 24% relative to the base rice weight)
           [sanna-03::structure::0].

identical: False
```

**What I had to add.** Every field above had to be added — the app logged nothing before this week.
`tracing.py` and the `PROMPT_VERSION` constant are new.

**What I could not reconstruct: the output itself.** Same prompt, same model, same params, different
wording. There is no seed or temperature control on this API surface, so a trace can prove what was
*asked* and what was *returned*, but cannot prove the return was inevitable. Both facts survived
(120g, 24%); only the phrasing and the citation formatting moved — and note the replay happened to
emit a single chunk id where the original emitted two in one bracket, which means **mode M4 is
intermittent**: the same prompt fails the citation check on one run and passes on the next.

## 4. The dated prediction

`prediction.md`, committed **before any fix**.

**Commit `bfad03cee424dfffeef5ea181f9e45c63054f38c`, dated 2026-08-26.**

Attacking **M3** (citation check passes while checking nothing, 5/20 = 25%) by extending
`VALUE_PATTERN` to word-spelled units and the degree symbol. Predicted: **25% (5/20) → at most 10%
(2/20)** when the same 20 stored traces are re-verified, with no other mode's count changing.
Testable with zero API calls, because `raw_output` is stored in every trace.

## 5. Why a public benchmark would have missed the top three modes

A public RAG benchmark scores whether the final answer matches a reference string, so M3 — a citation
check that passes having verified nothing — is invisible to it by construction: the answer was
*right* in every one of those five traces, and what failed was my own verifier, which no benchmark
runs. M1 and M2 depend on the exact vocabulary of these six cards, where "ratio" and "overnight" are
words a user types and the card never uses, and "what temperature" has a duration sitting next to it
— a benchmark's questions are written by whoever wrote its reference answers, so they use the
corpus's own vocabulary and never produce this mismatch. And M5's severity is only assessable against
this corpus, because "another recipe's chunk in the top-5" is harmless among six fermentation cards
and would be a data-leak class of bug in a corpus where recipes contradicted each other — a
leaderboard number cannot tell you which of those you have.

## 6. Bonus — 1 of 10 traced, not yet reportable

The bonus compares the top mode's frequency in the random sample against the curated demo set
(`sample_demo.json`, same seed `20260824`, drawn from the 19 questions in `eval_questions.json`,
`golden_set.jsonl` and the live demo cache — the questions actually used at reviews).

`bonus_demo_vs_random.py` computes the comparison for the three automatable modes. It currently
reads:

| mode | random sample | demo set |
|---|---|---|
| M3 citation check passes while checking nothing | 5/20 (25%) | 1/1 |
| M4 two chunk ids in one bracket void the check | 1/20 (5%) | 0/1 |
| M5 another recipe's chunk in the top-k | 10/20 (50%) | 0/1 |

**The demo column is not a result.** One trace is not a frequency: "1/1" reads as 100% and means
nothing. Nine of the ten demo traces are still missing because the Gemini free tier allows 20
requests a day and the daily counter resets at midnight Pacific, not at local midnight — a single
call got through on a per-minute allowance before the day counter blocked again.

`run_traces.py --set demo` is resumable and skips anything already traced, so completing this is one
command once the quota rolls over. The comparison paragraph the bonus asks for — what the team has
been telling itself — is deliberately not written yet, because writing it off n=1 would be exactly
the fiction the week is about.
