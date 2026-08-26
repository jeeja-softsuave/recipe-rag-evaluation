# Failure taxonomy — 20 traces, seeded random sample

Sample: 20 of 174 candidate questions, `random.Random(20260824)`. Traces in `traces.jsonl`,
open-coding sentences in `notes.md`. **7 of 20 traces (35%) showed no failure mode at all.**

| # | Mode | Count | % of 20 | Severity | Example trace_id |
|---|---|---|---|---|---|
| M1 | Asks with a word the card never uses, gets a flat refusal | 3 | 15% | annoys the cook | `t-37d6fe47d8` |
| M2 | Answers the neighbouring fact instead of the one asked | 2 | 10% | **ruins the dish** | `t-187716b1dd` |
| M3 | Citation check passes while checking nothing | 5 | 25% | **poisons silently** | `t-e1b8a19406` |
| M4 | Two chunk ids in one bracket void the whole citation check | 1 | 5% | annoys the cook | `t-c1b5435192` |
| M5 | Another recipe's chunk sits in the top-5 of a single-recipe question | 10 | 50% | no harm yet | `t-62532e8648` |

**Modes are not mutually exclusive** — a trace can show more than one, so the counts do not sum to
20. M5 co-occurs with everything because it is about what was retrieved, not what was answered.

## What each mode looks like

**M1 — asks with a word the card never uses, gets a flat refusal.** "what ratio does sanna use"
returned `NOT_IN_CORPUS` while the rank-1 chunk stated sanna's hydration as 50% plus 24% from
toddy. Same for kallappam's ratio and "can i leave moru overnight". The word on the card is
"hydration" or "2 hours", not "ratio" or "overnight".

**M2 — answers the neighbouring fact instead of the one asked.** "what temperature for moru" was
answered with a *duration*: "left to stand at room temperature for 2 hours". "can i leave idli
batter overnight" was answered "Yes, idli batter is fermented for 10 to 12 hours at 28C" — a yes to
a keeping-safety question, backed by a fermentation window that does not say yes.

**M3 — citation check passes while checking nothing.** Five traces produced a citation whose
`claimed_values` was empty, so `all_citations_ok` reported true having verified nothing: "300 grams"
(word unit), "30°C" (degree symbol), and three sentences carrying facts with no digits.

**M4 — two chunk ids in one bracket void the whole citation check.** "sanna toddy quantity" answered
`120g … 24%` — both correct — citing `[sanna-03::structure::0, sanna-03::structure::1]`. The
citation regex requires no whitespace inside the brackets, so it matched nothing, and the run was
recorded as `all_citations_ok=False` with zero checks performed.

**M5 — another recipe's chunk in the top-5.** Half the sample retrieved at least one chunk from a
recipe the question was not about. On "is sanna safe for a dairy allergy" the rank-1 chunk was
**moru's** allergen note — moru being the one dairy recipe in the corpus. The answer was still
correct. This mode caused **zero wrong answers** in this sample, which is why its severity is "no
harm yet" and not "ruins the dish".

## Ranked for action

By severity × frequency, **M3 first** (25%, silent — a wrong quantity in this shape reaches the cook
with a green check beside it), then **M2** (10%, ruins the dish but visible), then **M5** (50% but no
observed harm — it is the precursor to a cross-recipe quantity error, not yet an error).

The prediction in `prediction.md` attacks M3. Commit `bfad03cee424dfffeef5ea181f9e45c63054f38c`,
dated 2026-08-26, made before any fix.
