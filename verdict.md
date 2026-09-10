# Verdict

**Decision rule: does the path vary by input?**

For **6 of 10** requests it does not. Find, scale, at most one swap, in a fixed order. The
workflow matched the agent's pass rate on all six while spending **1/23 of the tokens, 1/10
of the latency and 1/15 of the cost per request**. An agent is not justified there.

For **4 of 10** it does. Three cascade requests, where step 3 depends on what step 2
returned because the substitute is itself an allergen, and one unsatisfiable request, where
the chain dead-ends. The fixed workflow scored **0/4**: it makes one swap and never
re-checks it. Only the agent solved them.

**The class that forces an agent: multi-constraint allergen adaptation** — where a
replacement must be re-checked against the remaining constraints.

Route by constraint count: workflow at zero or one, agent at two or more.
