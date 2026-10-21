# Pantry-to-Plate: architecture on one page

```
                         python pantry.py ask "..."          python capstone_eval.py --label X
                                       │                                  │
                                       ▼                                  │ (same entry: pantry.answer)
 ┌────────────────────────────── pantry.py  (HOST, one process) ─────────────────────────────┐
 │  trace_id = random  ──────────────────────────────────────────────────────────────┐      │
 │                                                                                    │      │
 │  Week 7 agent loop  (≤ 8 laps)                                                      │      │
 │    ┌──────────────┐  tools discovered at start-up via MCP tools/list (never hardcoded)     │
 │    │ MODEL CALL   │◄──── system prompt c1 + discovered tool schemas                  │      │
 │    │ gemini-3.6-  │ ──── function_call ──► route by tool owner ──┐                   │      │
 │    │ flash  $$$   │◄──── function_result ◄───────────────────────┤                   │      │
 │    └──────────────┘                                              │ MCP stdio,        │      │
 │  PII line: logs/capstone.jsonl gets a REDACTED question,         │ _meta.trace_id ───┘      │
 │  a salted hash, allergen categories, spans; never the raw text    │                          │
 └───────────────────────────────────────────────────────────────────┼──────────────────────────┘
                                                                     │
              ┌──────────────────────────────────────────────────────┼─────────────────────────┐
              ▼                                                      ▼                         │
 ┌──── pantry_server.py  (MY MCP server, also served to       ┌── vendor/ingredient_db ────┐   │
 │      any outside client: `python pantry.py serve`) ────┐    │  (third-party stand-in)    │   │
 │  search_recipes ──► Week 3 chunks + Week 4 hybrid      │    │  lookup_allergens          │   │
 │                     BM25+vector+RRF over               │    │  lookup_nutrition          │   │
 │                     recipes_capstone (44 chunks,       │    │  ✗ ignores _meta.trace_id  │   │
 │                     version-qualified ids)             │    │  ✗ logs raw queries        │   │
 │  check_allergens ─► EXACT MATCH on declaration fields  │    └────────────────────────────┘   │
 │                     (allergens / may_contain), current │                                     │
 │                     version unless asked                │◄── capstone_eval.py: assertions   │
 │  scale_recipe ────► grams × factor; TIMES UNCHANGED     │    FIRST (12, allergen never      │
 │  substitute_ingr. ► Week 7 table + Week 9 recoverable   │    judged) → judge_v2 MODEL CALL  │
 │  safe_temperature ► food_safety.json, number required   │    $  (batches of 10)             │
 │  every call: one span → logs/capstone_spans.jsonl       │                                    │
 │  under the caller's trace_id                            │                                    │
 └─────────────────────────────────────────────────────────┘                                    │
              ▲                                                                                  │
              └── data/capstone/: 6 cards + 2 reformulated-2025 versions (both versions kept),   │
                  declaration fields, time fields, food_safety.json ◄──────────────────────────────┘
```

## Where the model calls happen

**Only two places,** both in the host process:
1. **The agent loop:** one call per lap, typically 2–4 laps per question.
2. **The judge in `capstone_eval.py`:** one call per 10 cases.

Neither MCP server ever calls a model. Retrieval embeddings are local (all-MiniLM-L6-v2 via
ONNX), so they cost no API calls.

## Where the money goes

| Stage | Share of cost | Why |
|---|---|---|
| Agent model laps | ~100% of per-query cost | Every lap re-sends the system prompt, all 7 discovered tool schemas and the growing tool results. Week 10 measured the single agent at ~4.3k tokens and $0.0016 per question. |
| Judge | eval-time only, ~$0.0003 per 10 cases | Not paid per user query |
| Retrieval, allergen check, scaling, temperatures | $0 API | Local compute and file lookups |

**What breaks first at 50,000 queries a day** is in `capstone/tenx.md`, once it is measured.
The prediction from Weeks 10–11: **request rate** (requests per minute and per day), not
tokens and not dollars.

## Trust boundaries

- **The pantry server** is mine; it is the source of truth for allergens.
- **The vendor ingredient-db** is third-party. It is reachable, but out of date for the
  reformulated recipes (seam 3), and it breaks the trace id and the PII line (seams 6 and 7).
