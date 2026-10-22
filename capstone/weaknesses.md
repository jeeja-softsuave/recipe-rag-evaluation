# Top 3 known weaknesses: written Wednesday 2026-10-14, before anyone asked

Written from what integration exposed on Mon–Wed. Nobody prompted this list. It is not
edited afterwards; later findings go in a dated addendum below the line.

## 1. Superseded versions are retrieved next to current ones, and nothing but the prompt keeps them out of the answer

The Week 4 retriever has no notion of version. For every kallappam allergy query, both the
original (nut-free) and the reformulated-2025 (contains cashew) chunks land in the top 5.
For "kallappam ingredients", **the superseded original ranks #1**.

- `check_allergens` is safe: it defaults to the current version's declaration field.
- **Prose answers are not safe.** Ingredient lists, the "what goes into" questions, and the
  passage the model chooses to cite can all come from the superseded card. Only one sentence
  of the system prompt stands between a nut-allergic parent and the 2024 recipe.
- **Guarded by:** a01, a02, a09, v01, v02 (cites_expected_version), and a10 (the deliberate
  old-version question).
- **Measured rate:** unknown. See weakness 3.

## 2. The allergen check runs on the recipe as published, not on the recipe as the system changes it

`check_allergens` reads the declaration fields of the published card. `substitute_ingredient`
proposes swaps from the test kitchen's table and reports the swap's own allergens, but
**nothing re-checks the recipe after the swap against the user's full allergen list.**

- **Concrete path:** sanna is genuinely nut-free. A coconut-allergic user asks for a swap.
  The table's recorded swap for grated coconut is ground cashew paste, a tree nut. If the
  same user is also nut-allergic, the system has just made a nut-free recipe unsafe.
  Asserting the published verdict would still say "no_declared_allergen" for nuts.
- **Also:** the table is keyed on original ingredient names, so the reformulated kallappam's
  "coconut-cashew paste" has no recorded swap at all (seam 4).
- **Guarded by:** nothing yet. This is the bonus case to build, watch fail, and close.

## 3. As of Wednesday, nothing about the integrated system has been measured on a model

Every piece passes deterministic tests: 13/13 integration checks, and 12 assertions
validated on handmade good and bad answers. But the model provider (Gemini 3.6 Flash, the
model of weeks 7–10) has refused every request on all three keys on 9, 12, 13 and 14 October
(account-level cap).

So as of today:
- the 31-case suite has never run on real model output;
- the judge's agreement on integrated outputs is unknown, so **the 85% gate is unverified**;
- the taxonomy has no frequencies;
- the cost per query is an estimate, not a measurement.

A demo built on today's evidence would show plumbing, not behaviour.

---

## Also known, below the top 3 (from the seam list)

- **Peanut and tree nut are one category** (`nuts`). An exact match on a coarse vocabulary
  gives an exact but wrong answer for a peanut-only allergy (seam 2).
- **The vendor ingredient-db server breaks both the trace id and the PII line one hop away**
  (seams 6 and 7).
- **The safe-temperature lookup is first-match substring, order-dependent** (seam 9).

## Addendum (dated, added after Wednesday)

**2026-10-22, after the measured runs.**

- **Weakness 1 (superseded versions) was confirmed in an answer,** and it was worse than
  predicted. It did not surface as a wrong citation. It surfaced through a **substitution**:
  the after run's s03 told a coconut-allergic child's parent to use the original card's grated
  coconut (mode M8). The retrieval filter I scored offline (hit@3 8/11 → 9/11) is still not
  shipped. Remaining top weakness.
- **Weakness 2 (the substitution chain): the bonus case b01 passed on substance in every run.**
  The agent reasoned that the cashew swap is unsafe for a nut allergy. The chain failed
  elsewhere instead (M8, above).
- **Weakness 3 (nothing measured) is closed.** 32 cases × 4 runs on Flash-Lite, plus 4 on 3.6
  Flash. Judge agreement, after hand review: **84%, below the 85% gate** (all misses lenient).
- **New: the p3 guard over-blocks.** It withheld 3 safe answers in GREEN and cost p01 its pass.
  It is fail-closed by design, but too blunt.
- **Later the same day: the security layer (p4) is measured.** The red team went from 3/5
  to 5/5 attacks resisted. The full suite scored 30/32, allergy cases 16/17, with 0 unsafe
  answers: the first run with none. The hedged "Yes" (M3), which recurred in 3 of 4 runs, is
  closed by the contradiction guard. Cost +16% per query.
