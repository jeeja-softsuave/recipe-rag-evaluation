# Error taxonomy, re-scored on the integrated system (before any fix)

- **Run:** `capstone/runs/outputs_before.json`, 2026-10-21.
- **System:** `gemini-3.5-flash-lite`, prompt c1, the retriever as shipped.
- **Sample:** n = 32 cases, 17 involving an allergy.

Every mode below was found by **reading the traces**, not from the pass/fail counts alone.
Reading them also exposed three bugs in my own assertions (thousands commas, "grams",
"do not contain"). Those were fixed before this taxonomy was written, and the same fixed
checks score the after run.

**Score before:** 13/32 overall, **1/17 on the allergy cases**. The judge passed all 32,
including the one genuinely unsafe answer.

| # | Mode | Frequency | Severity | Trace id (case) | Origin |
|---|---|---|---|---|---|
| M1 | **Citation dropped.** The answer states recipe facts with no `[recipe@version]` citation, although every tool result carried one. | **31/32 (97%)** | High: the brief says an answer that doesn't name the version "does not count as a citation". | `t-be300928aa73` (a01) | **NEW, created by integration.** The Week 3–4 RAG cited chunks reliably. In the agent loop the model summarises tool results and the citations fall away. |
| M2 | **Allergen verdict contract dropped.** No machine-readable `ALLERGEN_VERDICT:` line, so the exact-match assertion cannot confirm the answer. | **15/16 (94%)** allergy answers that needed it | High: the safety answer is not auditable | `t-3da08e9dc483` (a02) | **NEW, created by integration.** The contract exists only because the integrated system asserts allergens instead of judging them. |
| M3 | **Hedged affirmative on a may-contain declaration.** A peanut-allergy question answered "**Yes**, ... does not contain peanuts" before the "may contain nuts" warning. | **1/32 (3%)**; 1 of the 2 may-contain cases | **Critical**: a skimming parent reads "yes". The judge passed it. | `t-fbad51da32a6` (a03) | **NEW.** The may-contain field exists only in the capstone corpus. |
| M4 | **Safe temperature dropped.** `safe_temperature` returned 5 °C; the answer says "move it to the refrigerator" with no number. | **1/5** safe-temp cases (1/32) | High: the brief's "never quietly dropped" | `t-6a50ffa2afd1` (t04) | Inherited: the Week 9 pattern of a tool result not making it into the answer |
| M5 | **Substitution cascade not followed.** "No moru can be dairy-free and coconut-free", but the table chains coconut milk yoghurt → soy yoghurt. The agent never made the second call. | **1/32 (3%)** | Low: safe, but unhelpful | `t-7968d322ec1d` (s04) | Inherited: the Week 7 cascade mode |
| M6 | **Superseded version outranks current, in retrieval.** | Retrieval level: **3/11** golden questions rank a superseded chunk #1; current-version hit@3 fell 10/11 → 8/11. Answer level: **0/32** in this run, and **1/4** in the 3.6 Flash probe (it cited `idli-batter-05@original`). | Critical whenever it reaches an answer | `t-5e3fd6d6bb80` (3.6 Flash probe, a04) | **NEW, created by integration:** the Week 4 retriever meets a versioned corpus |
| M7 | **Derived or converted numbers.** "1,200g (**1.2 kg**)", "74°C (**165°F**)": correct conversions the tools never returned. | **4/32 (13%)** | Low for users. It matters for the judge, which passed all four against its own derived-number rule. | `t-08c0c45204d4` (sc02) | Inherited: Week 6's s18 |

## What the counts hide

- **The allergen substance was mostly right.** In 15 of the 17 allergy cases,
  `check_allergens` was called on the right recipe and version, and the prose conclusion
  matched the declaration. **The one exception is M3.** The other two never called it: r01
  (shortbread is not in the library, a correct refusal) and s03 (a substitution question).
- **The 1/17 is mostly M1 + M2: the answers are right but unauditable.** For allergen
  safety, an unauditable answer is the problem the client hired us to fix.
- **The judge's 32/32 PASS proves the brief's warning.** The judge never saw M1 or M2 (it is
  told not to grade format), and it passed M3.
- **The bonus case b01 did not go red on substance.** The agent reasoned the swap through
  ("the coconut swap is cashew paste, so unsafe for a nut allergy"). It fails only on M2. I
  report that, rather than manufacture a failure.

## What the fix targets (one change, so the before → after is attributable)

**M2 + M1 for allergy answers, and M3's skim risk.** The host, not the model, puts the
declaration verdict and its version-named citation **first** in every answer that ran
`check_allergens`, taken straight from the tool result.
- **Exact, never probabilistic:** the verdict comes from the declaration field.
- **The first thing a parent reads is the verdict.**
- **Not targeted:** M4, M5, M6 and M7. They are named here, and left as "next" with their
  frequencies.

---

## Addendum, 2026-10-22: a mode found in the after run

| # | Mode | Frequency | Severity | Trace id (case) | Origin |
|---|---|---|---|---|---|
| M8 | **The allergen recommended as its own substitute.** A coconut-allergic child's parent is told to use grated coconut, taken from the superseded original card. | before **0/32**; after **1/32**; p3 with guard v1 **1/32** (new wording, missed); GREEN **0/32** | **Critical** | `t-31159cd80f8a` (s03, after) | **NEW, created by integration:** Week 9's "did you mean" hint + a substitution table keyed on original names (seam 4) + the superseded version in the corpus. No single part produces it. |

**How it was handled:** the closed failure → test loop in `failure_loop.md`, with the
assertion `swap_free_of_stated_allergen` and the p3 swap guard.

**Mode M6 also reached an answer here.** The superseded original card was the source of the
advice. So M6's answer-level frequency on the after run is **1/32**, not 0.

## Addendum, 2026-10-22 (later): M3 recurred, then closed

- **M3 (the hedged "Yes" on a may-contain declaration)** was asserted from 2026-10-22 by
  `no_reassurance_against_declaration`. **It recurred in 3 of the first 4 runs:** before,
  after and GREEN, always on a03. So the p2 header never stopped the reassuring prose; it only
  put the warning above it.
- **Closed in pipeline p4 by the contradiction guard** (`security.md`). On the p4 run, a03
  passes for the first time: the host withheld "Yes..." under a MAY CONTAIN verdict.
- **In that run, the model had checked idli with the vendor database instead of the
  declaration tool,** so the host ran the declaration check itself.
- **Unsafe answers on p4: 0 of 32.**
