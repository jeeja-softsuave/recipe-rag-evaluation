# Pantry-to-Plate: recipe RAG, agent and MCP, with evals

A course project (Soft Suave AI Engineering League, Task Set B) built week by week from
Week 3 to Week 12. This README gets a stranger from clone to a working answer. The Week 12
capstone integrates every earlier week behind **one entry point, `pantry.py`**.

## Run it (Windows PowerShell; one command per line)

```
git clone https://github.com/jeeja-softsuave/recipe-rag-evaluation.git
cd recipe-rag-evaluation
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a file named `.env` in the repo root with one line: `GEMINI_API_KEY=your-key`. Get a
free key at https://aistudio.google.com/apikey. Then:

```
.venv\Scripts\python.exe pantry.py index
.venv\Scripts\python.exe pantry.py ask "My son has a nut allergy. Can he eat kallappam?"
```

- **`index`** builds the local vector index. Run it once. The first run downloads the
  embedding model (about 80 MB).
- **`ask`** runs the whole system end to end. It prints the tool calls it made, the answer
  with clickable citations naming the recipe version, and the trace id with its cost and
  latency.

**Python 3.12** was used throughout. On macOS or Linux, use `.venv/bin/python` instead of
`.venv\Scripts\python.exe`, and set the same path in `capstone_config.json`.

## The single entry point

| Command | What it does | Model calls |
|---|---|---|
| `pantry.py ask "<question>"` | One question through the agent, MCP tools and retriever (model: gemini-3.5-flash-lite; override with `PANTRY_MODEL`) | 2–4 |
| `pantry.py trace <trace_id>` | Every span of one request, on both sides of the MCP hop: latency, tokens, cost | 0 |
| `pantry.py serve` | The pantry MCP server on stdio, for any MCP client | 0 |
| `pantry.py index` | Rebuild the capstone index | 0 |
| `capstone_eval.py --label <name>` | The eval suite on the integrated system: 32 cases, assertions, judge, report | ~95 |
| `capstone_eval.py --label <name> --report` | The report again from stored runs | 0 |
| `test_pantry.py` | The 18 integration checks, with the model stubbed | 0 |

## Use the MCP server from your own client

The server needs no API key: it does retrieval, exact-match allergen checks, scaling,
substitutions and safe temperatures, and never calls a model.

**MCP Inspector:**
```
npx @modelcontextprotocol/inspector .venv\Scripts\python.exe pantry.py serve
```

**Any client that takes a JSON server config** (Claude Desktop, Claude Code and others):
```json
{"mcpServers": {"pantry": {"command": "<repo>\\.venv\\Scripts\\python.exe",
                           "args": ["<repo>\\pantry.py", "serve"], "cwd": "<repo>"}}}
```

**Tools:** `search_recipes`, `check_allergens`, `scale_recipe`, `substitute_ingredient`,
`safe_temperature`. If you pass `_meta: {"trace_id": "..."}` on a call, the server logs
its span under that id in `logs/capstone_spans.jsonl`.

## What to read

| File | What it is |
|---|---|
| `capstone/architecture.md` | One page: boxes, arrows, where the model calls happen, where the money goes |
| `capstone/seam_list.md` | Tuesday's seam list, unedited |
| `capstone/weaknesses.md` | Top 3 weaknesses, dated Wednesday, written before anyone asked |
| `capstone/cases.jsonl` | The 32 eval cases; 17 involve an allergy. Built by `capstone/build_cases.py` from the corpus. |
| `capstone/eval_report.md`, `taxonomy.md`, `failure_loop.md`, `trace_and_scale.md`, `demo_script.md` | Results, failure modes, the closed loop, cost and scale, and the demo |
| `capstone_assertions.py` | The 13 deterministic checks. Allergen correctness is asserted, never judged. |
| `data/capstone/` | The corpus: 6 cards plus 2 reformulated-2025 versions, declaration fields, the safe-temperature chart |
| `results_week*.md` | Each earlier week's findings |

## Results (Week 12 capstone)

| | before | after one fix (p2) |
|---|---|---|
| Allergy cases, n = 17 | 1/17 | **15/17** |
| Whole suite, n = 32 | 13/32 | 28/32 |
| Judge agreement vs hand labels | 27/32 = **84%** (below the 85% gate; every miss lenient) | |

All runs use gemini-3.5-flash-lite. Full detail is in `capstone/eval_report.md`. The near-miss,
and how it was closed, is in `capstone/failure_loop.md`. Cost and scale are in
`capstone/trace_and_scale.md`.

## Honest limits

- **The corpus is 6 recipes, not 600.** The two reformulated-2025 versions and the
  safe-temperature chart are curated for the capstone, and labelled as such in the files.
- **Model quota.** On Gemini's free tier the limit is 20 requests per day per project.
  `ask` stops with a clear message, rather than retrying, when the quota is refused.
- **Cost figures are modelled** from token counts at list prices; the free tier bills nothing.
