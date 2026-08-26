# Failure taxonomy — 20 traces, seeded random sample

**The reported complaint did not reproduce.** The food editor said it "sometimes gets the quantities
wrong". Nine of the 20 sampled questions asked for a quantity and **all nine returned the correct
number**. Whatever is annoying the editor, it is not arithmetic — and none of the five modes below
would have been found by looking for wrong quantities.

Sample: 20 of 174 candidate questions, `random.Random(20260824)`. Population enumerated from the
cards, not hand-picked; it is a synthetic question space, not real traffic (`notes.md` §1).
**7 of 20 traces (35%) showed no failure mode at all.**

| # | Mode | Count | % of 20 | Severity | Example trace_id |
|---|---|---|---|---|---|
| M3 | Citation check passes while checking nothing | 5 | 25% | **poisons silently** | `t-e1b8a19406` |
| M2 | Answers the neighbouring fact instead of the one asked | 2 | 10% | **ruins the dish** | `t-187716b1dd` |
| M5 | Another recipe's chunk sits in the top-5 of a single-recipe question | 10 | 50% | no harm observed | `t-62532e8648` |
| M1 | Asks with a word the card never uses, gets a flat refusal | 3 | 15% | annoys the cook | `t-37d6fe47d8` |
| M4 | Two chunk ids in one bracket void the whole citation check | 1 | 5% | annoys the cook | `t-c1b5435192` |

Ordered by severity, not frequency. **Modes are not mutually exclusive** — a trace can show more than
one, so counts do not sum to 20. M5 co-occurs with everything because it describes what was
retrieved, not what was answered.

**Fix order: M3 first.** It is the only mode where a wrong answer would reach the cook with a green
check beside it — the verifier reported success having extracted zero claims to verify. M2 is worse
per incident but visible. M5 is the most frequent and caused **zero** wrong answers here, so it is a
precursor to a cross-recipe quantity error, not yet an error.

Per-mode detail and all 20 observation sentences: `notes.md`.
Prediction attacking M3: `prediction.md`, commit `bfad03cee424dfffeef5ea181f9e45c63054f38c`,
dated 2026-08-26, committed before any fix.
