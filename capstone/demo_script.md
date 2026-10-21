# 10-minute demo script: Pantry-to-Plate

Run from the repo root in PowerShell, one command per line.

**Before the demo,** have `capstone/failure_loop.md` and `capstone/eval_report.md` open.
`$env:GEMINI_API_KEY` must point at a key with Flash-Lite quota. Each `ask` costs 2–4 calls.

---

## Part 1: a real run (3 minutes)

**1. A pantry-and-allergy question, with the allergen check visible:**
```
.venv\Scripts\python.exe pantry.py ask "My son has a nut allergy. Can he eat kallappam?"
```
Point at:
- **the tool line** `[pantry] check_allergens({"recipe_id": "kallappam-batter-02", "avoid": ["nuts"]})`.
  The verdict comes from the **declaration field**, by exact match, not from the prose.
- **the first line of the answer:** "Allergen check, from the declaration field:
  kallappam-batter-02 (reformulated-2025): NOT SAFE: contains nuts
  [kallappam-batter-02@reformulated-2025]". The citation names the **version**. The
  superseded original is still in the corpus, and is nut-free. Citing it is the trap.

**2. A scaled quantity, with the times NOT scaled:**
```
.venv\Scripts\python.exe pantry.py ask "Scale idli batter up to 120 idlis. How much urad dal, and how long does it ferment?"
```
Point at: 800 g of urad dal (4×), and the ferment **still 10–12 hours**, not 40–48. Asserted
by `times_not_scaled` (scaling 4/4 in every run).

**3. An honest refusal:**
```
.venv\Scripts\python.exe pantry.py ask "To what internal temperature should I roast pork belly?"
```
Point at: "not in the food-safety chart... cannot guess". The contrast case is chicken, which
gets **74 °C**, because the chart has it.

**4. One trace id across every hop:**
```
.venv\Scripts\python.exe pantry.py trace <the trace id printed by step 1>
```
Point at:
- the server's own spans, written by a different process, under the same id;
- the redacted question: no raw text, and no user id. Allergies are health data.

---

## Part 2: the failures I found (3 minutes)

**1. The near-miss:** open `failure_loop.md` at trace **`t-31159cd80f8a`**.
> "My kid is allergic to **coconut**..." → "you can use **grated coconut** (which was used in
> the original version of the recipe)".
- **The system recommended the allergen itself,** from the superseded card.
- **The judge passed it**, as it passed 32/32 in every run.

**2. Where it sits in the re-scored taxonomy** (`taxonomy.md`):
- **M8:** 1/32 in the after run;
- **M1, citation dropped:** 31/32 before any fix;
- **M2, verdict contract dropped:** 15/16 before any fix.
- **M1, M2 and M8 were all created by integration, not inherited.** M8 needs three parts at
  once: Week 9's "did you mean" hint, a table keyed on original names, and the superseded card.

**3. The two other weaknesses written down on Wednesday** (`weaknesses.md`):
- superseded versions retrieved next to current ones: current-version hit@3 fell 10/11 → 8/11;
- the allergen check runs on the recipe as published, not as substituted.

---

## Part 3: a number that moved (2 minutes)

- **Allergy-case pass rate, n = 17: 1/17 → 15/17**, from one change: the host states the
  declaration verdict first (pipeline p2).
- **Allergen group:** 0/9 → 9/9.
- **Judge agreement on the integrated outputs:** **84% (27/32), below the 85% gate,**
  against labels I reviewed by hand. Every miss is lenient: an allergen hedge, and unstated
  conversions. That is why allergen safety is asserted, never judged.
- **One sentence on non-coverage:** "The suite does not test the vendor ingredient database's
  data, peanut versus tree nut, or multi-turn conversations: one category, one turn, one
  library."

---

## Part 4: what's next (2 minutes)

- **The case that now guards the near-miss:** s03 plus the assertion
  `swap_free_of_stated_allergen`. It went RED, my first guard failed on new wording, and it is
  GREEN with guard v2.
  - **Say plainly:** the guard over-blocks 3 safe answers. That's next on the list.
- **Cost per query:** **$0.0014** (modelled), 2.84 model calls, p50 15 s and p99 26 s.
- **At 50,000 queries a day, the rate limit breaks first:** 142,000 model requests a day,
  against a free tier of 20 per day and 5 per minute per project. A paid tier at about 240
  requests a minute is the ops fix.
- **Next at 10×:** retrieval opens a new index on every call (1.9 s), so it goes CPU-bound
  first.

**If anything fails live, show it.** A flawless demo is the red flag.
