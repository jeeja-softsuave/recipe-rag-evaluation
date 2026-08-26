# Dated prediction — committed before any fix

**Date: 2026-08-26**

## The mode I will attack next week

**"Citation check passes while checking nothing"** — 5 of 20 traces (25%).

The verifier extracts numeric claims with `VALUE_PATTERN` and confirms they appear in the cited
chunk. In 5 of the 20 traces it extracted *nothing* and passed anyway, because the model wrote the
quantity in a form the pattern does not match: the word `grams` instead of `g` (t-e1b8a19406, "300
grams"), a degree symbol in `30°C` (t-8d580a7ac5), or a sentence carrying a fact with no digit at
all (t-187716b1dd, t-62532e8648, t-f3c0b146f5).

## The specific change

Extend `VALUE_PATTERN` to match word-spelled units (`grams`, `gram`, `kilograms`, `percent`,
`degrees`) and to tolerate a degree symbol between the number and the unit (`30°C`, `30 °C`).
Nothing else changes: no prompt change, no retrieval change, no chunker change.

## The exact delta I expect

Re-verifying **the same 20 stored traces** (no new API calls — `raw_output` is stored):

| metric | now | after the change |
|---|---|---|
| traces with an empty-claimed-values citation check | **5/20 (25%)** | **at most 2/20 (10%)** |
| traces where a claimed value is checked and matches | 13/20 | at least 16/20 |
| any other mode's count | — | unchanged |

Specifically I expect t-e1b8a19406 (`300 grams`) and t-8d580a7ac5 (`30°C`) to move from
unchecked to checked-and-passing, and I expect t-187716b1dd, t-62532e8648 and t-f3c0b146f5 to stay
unchecked, because those sentences contain no numeric claim of any kind and no regex can invent one.

## How I can be wrong

If fewer than 3 of the 5 move, the change is a failure and the real cause is not unit formatting.
If any currently-passing trace starts failing, the widened pattern is over-matching and must be
reverted. If the two I named do not move, my reading of those two traces was wrong.
