# One end-to-end trace, cost per query, and what breaks at 50,000 queries a day

## The trace: one id across the agent hop and the MCP hop

From the GREEN run, case a01 ("My son has a nut allergy. Can he eat kallappam?"), pipeline p3.
Reproduce with `python pantry.py trace t-c02d300fad1b`.

```
trace t-c02d300fad1b  prompt c1  gemini-3.5-flash-lite
question (redacted): [PERSON] has a nut [HEALTH]. Can he eat kallappam?
span                                latency ms   tokens    cost usd
model:lap1                              9087.1     1383    0.000457
tool:search_recipes                     2499.3        0    0.000000
model:lap2                              3460.7     1296    0.000475
tool:check_allergens                       9.3        0    0.000000
model:lap3                              3485.5     1408    0.000609
  server mcp:search_recipes             2492.0        0    0.000000      <- written by the server process
  server mcp:check_allergens               0.6        0    0.000000      <- under the same trace id
total                                  21852.0     4087    0.001541
citations: ['kallappam-batter-02@reformulated-2025']
```

- **The agent's spans** are in `logs/capstone.jsonl`. **The server's spans** are in
  `logs/capstone_spans.jsonl`, written by a different process. The trace id travelled in the
  MCP request's `_meta`.
- **The PII line, as logged:**
  - `question_redacted`: "[PERSON] has a nut [HEALTH]. Can he eat kallappam?";
  - `question_hash`: a salted hash, `8d4f63ce0bbd6c5f`;
  - `allergen_categories`: `["nuts"]`;
  - **no raw question and no user id.**
- **Not covered:** the vendor ingredient-db server ignores `_meta` (seam 6). A call to it
  would carry no trace id. This request made none.

## Cost per query, by stage (GREEN run, n = 32)

| Stage | Per query | Share |
|---|---|---|
| Model laps (generation) | 2.84 calls, 3,509 input + 135 output tokens, **$0.001392** | **~100% of cost**, 87% of time |
| `search_recipes` (retrieval) | 0.81 calls, **1,880 ms** each, $0 | 13% of time |
| `check_allergens`, `scale_recipe`, `safe_temperature`, `substitute_ingredient` | 7–13 ms each, $0 | ~0% |

- **Latency:** p50 **15.1 s**, p99 **26.1 s** (nearest-rank, n = 32).
- **Cost is modelled** at the list prices used since Week 7 ($0.30 per million input tokens,
  $2.50 per million output). Those are 3.6 Flash's prices; Flash-Lite lists lower, so this is
  an upper bound. The free tier bills nothing.

## What breaks first at 50,000 queries a day

**The model provider's rate limit, by four orders of magnitude.**
- 50,000 queries × 2.84 model calls = **142,000 model requests a day**. That's 1.6 per second
  on average, and about **240 per minute** in a peak hour carrying 10% of the day.
- The free tier allows **20 requests a day and 5 a minute per project** (from Google's own
  rate-limit page). That's 1/7,100 of the daily need.
- **The fix is a paid tier** with at least ~240 requests per minute sustained, plus a
  request queue. That's an ops decision, not code.

**Second, retrieval at 10× (500,000 queries a day).** Every `search_recipes` call opens a new
index client and loads the embedding model: **1.88 s per call**. And `pantry.py` starts the
MCP server processes once per question. At 500,000 a day, about 5.8 questions a second, that
is roughly **9 CPU-seconds of retrieval every second**: CPU-bound before the model is.
- **The fix:** keep one long-lived server and one loaded index (connection reuse). The
  retriever and the embedder stay the same; no re-embedding.

**Not what breaks:**
- **Cost:** 50,000 × $0.001392 = **$70 a day**, an upper bound.
- **Tokens:** 3.6k per query is far below the per-minute token limits.
