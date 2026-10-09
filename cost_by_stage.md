# Week 11: cost per query, by stage

Cost is modelled from the token counts the API reported, at the stated list prices
($0.30 per million input tokens, $2.50 per million output). The free tier bills nothing,
so this is an assumption, not an invoice.

## The found request: `t-e79ea9256d`

| Stage | Latency | Tokens (in / out) | Cost | Note |
|---|---|---|---|---|
| retrieval | 517.3 ms | 0 / 0 | **$0.0000000** | BM25 + local MiniLM embeddings + RRF; no API call |
| generation | 58,004.2 ms | 528 / 41 | **$0.0002609** | the only paid stage |
| tools | 1.4 ms | 0 / 0 | **$0.0000000** | citation check against the index; deterministic |
| **total** | **58,522.9 ms** | **569** | **$0.0002609** | |

**Caveat.** This line is the planted one. Its generation latency and tokens were copied from
a real v2 request (`t-9cb2486400`), so they are real numbers from last week, just not from
this exact answer. Its retrieval and tools spans were measured for real when it was
planted.

## Across the week (21 real requests)

| Stage | Mean cost | Share of cost | p50 latency | Max latency |
|---|---|---|---|---|
| retrieval | $0.0000000 | 0% | 169.5 ms | 1,267.4 ms |
| generation | $0.0002614 | **100%** | 6,852.1 ms | 58,004.2 ms |
| tools | $0.0000000 | 0% | 0.8 ms | 4.0 ms |
| **per query** | **$0.0002614** | | | |

By prompt version: v1 costs $0.0002472 per query, v2 $0.0002685 (+8.6%). v2's longer
system prompt adds input tokens on every request, whether or not it suggests a swap.

## What this says

- **Generation is 100% of the money and about 97% of the time.** Retrieval and the citation
  check run locally and cost nothing in API terms; their compute is real but not billed
  here. Any cost or latency saving has to come from generation: fewer input tokens per
  request, or fewer requests.
- **The latency tail is not the model thinking.** The p50 generation span is 6.9 s; the max
  is 58.0 s. The two requests over 50 s were rate-limit waits (the retry sleeps sit inside
  the generation span). That is a quota symptom, and it is what `tenx.md` is about.
- **Per-stage attribution came before any optimisation** (the brief's common mistake #1).
  No optimisation was made this week: the v3 change is a correctness fix, and its cost
  effect will be visible against these numbers.
