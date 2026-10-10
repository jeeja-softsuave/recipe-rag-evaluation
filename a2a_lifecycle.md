# Week 10 bonus: the AgentCard, and the failed case on the A2A task lifecycle

**AgentCard:** `agent_card.json`. It is what the orchestrator would serve at
`/.well-known/agent-card.json`:
- **Skills:** `ingredient-substitution`, `allergen-check`.
- **Input/output modes:** `text/plain`.
- **Auth:** an HTTP bearer JWT with scopes `recipes:read` and `ingredients:nutrition`.
- **Capabilities:** no streaming, no push notifications.

It is not served: the orchestrator runs in-process, and the card says so.

## The failed case (`squad_fault:s12`) on the A2A lifecycle

**What happened:** the parent task went `submitted → working → completed`, with a partial
answer whose own text says "the allergen check could not be performed".

**What should have happened:**

| Task | Should have ended | Why |
|---|---|---|
| allergen-check sub-task | **`failed`** | A 500 is a system fault. The user cannot fix it, so `input-required` is the wrong state for it. |
| parent task | **`input-required`**, not `completed` | The allergy check never ran, and the suggested swap (coconut milk yoghurt) carries an allergen the user was never asked about. The task should pause and ask: "the allergen check is unavailable; is anyone you are serving allergic to coconut?" and resume on the answer. `completed` with "to make Moru safe" in the first line is the wrong terminal state for a safety-critical question. |

**What A2A buys over a plain REST call to the worker:**
1. A REST call gives the orchestrator a bare 500, and the orchestrator must invent its own
   conventions for partial and paused work. A2A gives every task an id and standard states
   (`input-required`, `failed`, `completed`), so "pause and ask the user" is a protocol
   state the client already understands, not an ad-hoc string in the answer.
2. The AgentCard lets a caller discover the worker's skills and auth before calling it, so a
   missing allergen skill or an expired token fails at discovery, not mid-task.
