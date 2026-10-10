# Week 10: single agent vs kitchen squad

**The 10 cases** are a seeded sample of the 34 Week 6 cases, fixed before any run
(`race10_cases.json`, seed 20260824). None was written, edited or swapped:
r01, r03, r04, s04, s06, s07, s12, s16, s18, s21.

**The judge** is Week 6's `judge_v2.txt`, unchanged, on `gemini-3.6-flash`. It was run blind:
all 21 answers were shuffled under neutral ids, and each answer was judged against every
tool result its own run obtained.

**Both arms** use the same model (`gemini-3.6-flash`), the same two MCP servers and the same
5 tools.
- **single:** Week 9's `mcp_agent.py`, unchanged.
- **squad:** `orchestrator.py` (plan → substitution worker → allergen worker → synthesis).

| Metric | Single agent | Squad | Squad vs single |
|---|---|---|---|
| **Pass rate** (judge_v2, blind) | **9/10** | **8/10** | −1 case |
| **p50 latency** | **24.1 s** | **48.9 s** | 2.0× |
| **p99 latency** | **49.0 s** | **92.1 s** | 1.9× |
| **Total tokens** (10 cases) | **42,717** | **43,667** | 1.0× |
| **Cost per question** | **$0.00160** | **$0.00249** | +56% |
| Model calls (10 cases) | 30 | 59 | 2.0× |
| Output tokens (10 cases) | 1,436 | 5,381 | 3.7× |

**Multiplier:** squad tokens / single tokens = 43,667 / 42,717 = **1.0×**. The single largest
share is **"orchestrator → substitution worker", 19,898 tokens, 45.6% of all squad tokens**
(from `handoffs.log`). Next come orchestrator → allergen worker (35.7%), synthesis (12.3%)
and the plan (6.4%).

## Why the token count and the cost disagree

The squad sends about the same number of tokens as the single agent but costs 56% more per
question, because the mix is different:
- **The single agent spends tokens on input.** It re-sends all 5 tool schemas and both
  allergen resources on every lap: 41,281 input tokens.
- **The squad spends them on output.** Each narrow worker carries only its own 2–3 tools, so
  input is lower (38,286). But two worker reports plus a synthesis means 3.7× more
  **output**, and output is priced 8.3× higher per token ($2.50 vs $0.30 per million).

## Where the arms differ on pass rate

| Case | Single | Squad | Why |
|---|---|---|---|
| s18 "half batch of sanna using yeast, how much yeast" | PASS | **FAIL** | **Both answers say "1.5 g of dry yeast", and in both it is derived.** The single agent called `scale_recipe`, but that returns 60 g of *slurry*, not 1.5 g of yeast. The squad never scaled. The judge passed the single agent's answer ("scaled amounts match the scale tool output") and failed the squad's for the derived-number rule. That is a judge inconsistency, not a difference between the arms. |
| s21 "refrigerate moru straight away" | FAIL | FAIL | No tool returns method text, and both arms answered from general knowledge. |

**So the 9/10 vs 8/10 gap is one judge inconsistency.** Read honestly, the two arms tie on
answer quality: both are 8/10 if s18 is failed for both, or 9/10 if it is passed for both.
The race is decided by the other three numbers.

## How the numbers were measured

- **p50 and p99 are nearest-rank over 10 runs.** **With n = 10, p99 is the slowest run.**
  Single: s04, 49.0 s. Squad: s12, 92.1 s.
- **Cost is modelled** from reported tokens at $0.30/M input and $2.50/M output (the free
  tier bills nothing). It excludes the judge, which is the same for both arms.
- **Latency carries noise.** Runs span 3 API projects (keys 1–3) and three days
  (2026-09-26, 10-08, 10-10). Rate-limit waits are inside the measured time, as a user
  would experience them.
