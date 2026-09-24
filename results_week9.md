# Week 9: bolt on the ingredient database server without touching the agent

The recipe-search MCP server gets a second server: the ingredient database. It is added to
the agent through configuration alone. Predictions were written before any model call and
committed with the baseline ([prediction_week9.txt](prediction_week9.txt), commit `5963d57`).

## Commit sequence (the ordering is part of the evidence)

| Commit | What | Touches `mcp_agent.py`? |
|---|---|---|
| `5963d57` | Baseline: server one, `mcp_agent.py`, `mcp_config.json` with server one only, 15 stub checks, predictions | created here |
| `419ac32` | The ingredient-db server's own files in `vendor/ingredient_db/` (stand-in for the content team's release) | no |
| `d5036fb` | **Config only:** +5 lines in `mcp_config.json` | **no** |
| later | Evidence, then the requirement 5 rewrite of **server one** (`recipe_server.py`) | no |

## Headline numbers

- **Agent diff:** 0 changed lines in `mcp_agent.py` between `5963d57` and `d5036fb`. The
  blob hash `9d28218` is identical at both commits. See [agent_diff.txt](agent_diff.txt).
- **Config diff:** +5 lines, 0 removed. See [config_diff.txt](config_diff.txt).
- **Tool count:** 3 → 5, taken from `tools/list` (raw output in
  [tools_before.json](tools_before.json) and [tools_after.json](tools_after.json)):
  - before, `recipe-search`: `search_recipes`, `scale_recipe`, `substitute_ingredient`
  - after, `recipe-search`: the same 3; `ingredient-db`: `lookup_allergens`, `lookup_nutrition`
  - Attached resources went from 1 to 2: `recipe://allergen-notes`, then also
    `ingredient-db://allergen-matrix`. These are attached to the prompt by the app; the
    model does not call them as tools.
- **Requirement 1, the same question before and after adding server two:** *"How much
  protein is in 100g of the urad dal used in idli batter?"*

  | | Server one only | Both servers |
  |---|---|---|
  | Tool path | `[recipe-search] search_recipes` | `[recipe-search] search_recipes` → **`[ingredient-db] lookup_nutrition`** |
  | Answer | declined to give a number: no tool returns nutrition | **25.2 g**, identical to the tool result |
  | Laps / total tokens | 2 / 1,923 | 3 / 3,715 |

  The server-two call appears in `mcp_traces.jsonl` (label `P2-after both-servers (req 1)`).
  Server two's own `queries.log` independently recorded `lookup_nutrition  Whole white urad dal`.
- **Wire capture:** [wire.json](wire.json) holds the 7 raw lines (initialize → initialized →
  tools/list → tools/call), with every top-level field annotated. The model is called only
  in the host (`mcp_agent.py`), never in either server. The capture client uses no model and
  declares no sampling capability.
- **Recoverable error (requirement 5):** a controlled replay of the same failing call
  `substitute_ingredient("curd", "dairy")`, full detail in
  [error_before_after.md](error_before_after.md):
  - before: the model invented 4 unchecked substitutes, 3 of them containing nuts or peanut;
  - after: 0 invented, and the grounded answer "coconut milk yoghurt (contains coconut)"
    after a single retry.
- **Risk note:** [risk_note.md](risk_note.md), 5 lines. Verdict: **don't ship as-is.**

## Predictions, scored

| # | Prediction | Result | Verdict |
|---|---|---|---|
| P1 | 3 → 3 + N tools, 0 agent lines | 3 → 5, 0 lines | hit (by construction) |
| P2 before | Server one only: the agent refuses rather than invents a protein number (60%) | refused: "the available tools do not return nutritional information" | hit |
| P2 after | Both servers: `search_recipes` → nutrition tool, exact number (80%) | exactly that, 25.2 g | hit |
| P3 | First-lap input tokens +40% to +80% | Prompt (instruction + tool specs) 5,115 → 6,466 chars, **+26%**. Mean input tokens per lap 942 → 1,214, **+29%**. | **miss**: overestimated |
| P4 before | Failing `curd` call, then "no substitute exists", a false negative (55%) | Failing call **yes**. Then the model **invented** substitutes, including nut ones, despite the system prompt. | **miss**, in the dangerous direction |
| P4 after | Model retries with "Thick sour curd" (75%) | Replay: yes, one retry. Natural run: the new docstring stopped the failing call from being made at all. | hit |

On P3: the stated metric, first-lap input tokens, is not recorded. `mcp_agent.py` sums
tokens per run, like the Week 7 agent. So the two proxies above stand in for it; both agree,
and both fall below the predicted range.

## Findings

1. **The system prompt did not stop fabrication; the tool result did.** Both the natural
   run and the replay broke the rule "never state a substitution no tool returned" after the
   old error message. Only the rewritten tool result (`recoverable`, `did_you_mean`) changed
   the behaviour. This is the brief's common mistake #4 happening on my own server.
2. **One server's resource hid a bug in the other server.** With both servers connected,
   the naming failure never happened. Server two's attached allergen matrix contains the
   exact string `Thick sour curd`, and the model copied it. It is good behaviour, but the
   flaw in server one only shows up without server two. That is why requirement 5 is
   measured with server one only (`mcp_config.server_one.json`, equal to `5963d57`'s config).
3. **The rewritten docstring worked before the error message could.** In the natural "after"
   run, the model called `search_recipes` first because the description said to use the
   card's name. The prompt stopped the failure from happening; the error message is the
   second line of defence.
4. **The SDK's parsed objects are not the wire.** The SDK's parsed results showed `ttlMs`,
   `cacheScope` and `resultType`, which never appear on the wire. The wire carries
   `outputSchema` and `structuredContent`, which my first SDK dump hid. The annotations
   follow the raw capture.
5. **Third-party defects found by testing, not by reading.** The ingredient-db server
   suggests `Green chilli` for `creme fraiche lite`, and maps bare `yoghurt` to dairy curd.
   Both are left unfixed on purpose, because it plays third-party code. Both are in the risk
   note.

## Design choices worth saying out loud

- **A new `mcp_agent.py` instead of converting `agent.py`.** `agent.py` imports `TOOL_SPECS`
  (a hard-coded list, the brief's common mistake #1), and `workflow.py` imports from it.
  Converting it would change the code behind the committed Week 7/8 numbers.
  `mcp_agent.py` names no tools and counts none. Its system prompt describes the job, not
  the tools.
- **Resources vs tools.** The allergen notes and the allergen matrix are standing context,
  so they are attached through the config (`attachResources`). Nutrition is per-query data,
  so it is a tool. The agent only attaches resources the config lists: a server cannot push
  context into the prompt by itself.
- **Errors map straight onto the model.** MCP `isError` becomes Gemini's
  `function_result.is_error`. A dead server comes back to the model as
  `server X failed: ...`, which is distinguishable from a no-match.
- **No model call in either server.** They are deterministic, and `capture_wire.py` proves
  it: a bare JSON-RPC client gets full answers with no model anywhere.

## Caveats

- **The server-two "third party" is a stand-in written in-house.** Its nutrition data is
  approximate and curated, like `substitutions.json`. This is labelled in the data file
  and in the risk note.
- **n = 1 per condition.** Every row above is a single run. The replay controls the
  comparison; it does not create a rate.
- **Cost is modelled, not billed**, using the same list-price assumption as Week 7.
- **API spend:** 17 Gemini calls in total, all on one project in one day (20/day limit).

## Reproduce

```
python test_mcp.py                                   # 15 checks, 0 API calls
python mcp_agent.py --list-tools                     # tools/list, 0 API calls
python mcp_agent.py --list-tools --config mcp_config.server_one.json
python capture_wire.py ingredient-db lookup_nutrition "{\"ingredient\": \"urad dal\"}"
git diff --stat 5963d57 d5036fb -- mcp_agent.py      # empty
python mcp_agent.py "How much protein is in 100g of the urad dal used in idli batter?"   # API
python replay_failing_call.py                        # API, about 5 calls
```

Bonus (gateway plus scoped token): not attempted.
