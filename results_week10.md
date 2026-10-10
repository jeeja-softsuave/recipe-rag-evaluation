# Week 10: the kitchen squad vs the single agent

**Verdict: KILL** (see `verdict_week10.md`). The answers tie, while the squad is 2× slower and
costs 56% more per question. Its token bill is flat (1.0×), not the 9× blow-up the brief
warns about.

## Deliverables

| File | Contents |
|---|---|
| `race_table.md` | the 4 metrics × 2 arms on the same 10 Week 6 cases, plus the multiplier line |
| `handoffs.log` | 64 hand-offs, each with its payload size, model calls and input/output/total tokens |
| `failure_case.md` | the injected 500: **retried once, then degraded; no lie** |
| `verdict_week10.md` | keep/kill in 9 lines, with sunk cost named first |
| `agent_card.json`, `a2a_lifecycle.md` | bonus: the AgentCard, and the failed case on the A2A lifecycle |
| `race10_results.json`, `race10_verdicts.json` | every run, and every blind verdict with its blind id |

## The numbers

| | Single | Squad |
|---|---|---|
| Pass rate (judge_v2, blind) | 9/10 | 8/10 |
| p50 / p99 latency | 24.1 s / 49.0 s | 48.9 s / 92.1 s |
| Total tokens | 42,717 | 43,667 |
| Cost per question | $0.00160 | $0.00249 |

**Multiplier:** 43,667 / 42,717 = **1.0×**. The dominant hand-off is **orchestrator →
substitution worker, 45.6% of squad tokens**.

## Predictions, scored (committed before any run, in `prediction_week10.txt`)

| # | Predicted | Actual | Verdict |
|---|---|---|---|
| P1 | single 7/10, squad 6/10, within one case | 9/10 vs 8/10, and the gap is a judge inconsistency | gap **hit**, levels **miss** (both arms did better) |
| P2 | multiplier 2.2× (range 1.8–2.8×) | **1.0×** | **miss**. The single agent's per-lap re-send of 5 tool schemas and 2 resources costs as much as the squad's extra calls. |
| P3 | dominant hand-off: orchestrator → allergen worker, ~45% | orchestrator → **substitution** worker, 45.6% | **miss** on which hand-off; the share was right. The substitution worker ran on 8 of 10 cases, the allergen worker on 6. |
| P4 | squad p50 ~2× single; p99 worse than 2× | p50 2.0×; p99 1.9× | p50 **hit**, p99 **narrow miss** |
| P5 | 60% honest degrade, 40% lie | retried, then degraded honestly | **hit** |
| P6 | kill | kill | **hit** |

## Findings

1. **The brief's premise did not hold here, and the reason is measurable.** Multi-agent is
   expected to multiply tokens. These narrow workers (2–3 tools, resources only where needed)
   held the bill at 1.0×. The cost difference comes from output, not re-sends: 3.7× more
   output tokens, priced 8.3× higher than input.
2. **Token count and cost point in different directions:** equal tokens, +56% cost. A
   report with tokens alone would have called it a draw.
3. **The pass-rate gap is the judge, not the arms.** Both arms answered s18 with the same
   derived "1.5 g"; the judge passed one and failed the other. Week 6 already found this
   judge's derived-number rule fragile, and it shows again here.
4. **The failure handling worked, with one overreach.** It retried, degraded, and disclosed
   that the allergen check was unavailable. But its opening sentence still said "to make
   Moru safe". On the A2A lifecycle, that case should have paused at `input-required`
   rather than completing (`a2a_lifecycle.md`).

## Caveats

- **The orchestrator did not exist before this week.** I built it this week, reusing Week 9's
  servers and tools, so the arms differ only in how the work is split.
- **The 10 cases are a seeded sample of Week 6's 34**, because Week 6 has 34 cases, not 10.
- **n = 10.** Every per-case difference is a single run.
- **Latency spans 3 API projects and three days** (2026-09-26, 10-08, 10-10).
- **Cost is modelled at list prices.** The free tier bills nothing.
- **No framework** (CrewAI, AutoGen) was used, so that every hand-off's tokens are
  attributable. The result is for this orchestrator design, not for multi-agent frameworks
  in general.
- **Git ordering:** the pushed commit `7fe1d24` (placeholder message) holds the predictions
  together with partial results. The commit proving the predictions came first is local
  `4a2c5e9`, made 2026-09-26 16:16:30 UTC, about 12 s before the first run started. It was
  never pushed.
