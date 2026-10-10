**Sunk cost, named first:** I built the orchestrator, its 17 tests and its fault handling over three working sessions (2026-09-26 to 10-10), and I want that work to have been worth it. That is the bias to discount below.
**Pass rate:** a tie, not a win: single 9/10, squad 8/10, and the one-case gap is a judge inconsistency on s18, where both arms derived the same 1.5 g.
**Latency:** squad p50 48.9 s vs 24.1 s, and p99 92.1 s vs 49.0 s: 2× slower at both ends, because every step is serial (59 model calls vs 30).
**Cost:** squad $0.00249 vs $0.00160 per question, +56%, although total tokens are equal (1.0×). The narrow workers save input, and the extra reports cost it back as output.
**What it does better:** it handled a dead allergen worker honestly (retry, then degrade), and its narrow contexts kept the token bill flat, which is the opposite of the expected 9× blow-up.
**What the single agent would need for the same:** nothing; it has no worker to lose, and it already scored 9/10.
**Verdict: KILL** the squad for this workload. Same answers, 2× the latency and +56% the cost buy nothing a user would notice.
**Keep the parts:** the narrow-context pattern and the 500-handling, for a future task where independent workers could run in parallel.
(Filed as verdict_week10.md, because verdict.md is the committed Week 7 verdict.)
