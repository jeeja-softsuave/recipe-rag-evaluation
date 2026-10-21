# The Week 4 retriever on the integrated corpus: hit-rate@3 re-measured

Measured Thursday 2026-10-15 (14 Oct 21:40 UTC). No model calls: retrieval is local.
**The retriever is unchanged:** Week 4's hybrid BM25 + vector + RRF, the same embedder and
the same Week 3 chunker. **What changed is the corpus:** the same 6 cards, plus 2
reformulated-2025 versions, with version-qualified chunk ids. The golden set is Week 4's 11
scored questions, unchanged; a gold chunk is matched in the version or versions named below.

| Index | hit@3 |
|---|---|
| Week 4 index (`recipes_structure_aware`) | **10/11**, reproducing Week 4's committed result |
| Capstone index, gold chunk in **any** version | **9/11** |
| Capstone index, gold chunk in the **current** version | **8/11** |
| Golden questions where a **superseded** version ranks #1 | **3/11** |

**Integration cost two golden questions, and neither is the retriever's "fault" in Week 4's
sense:**

1. **g01, "how much rock salt in the idli batter".** The superseded idli ingredient chunk
   ranks **#1**, and the current one ranks **#4**. The tables are identical, so nothing in
   the text separates the versions, and nothing in the retriever prefers the current one.
   A user gets the right number from the wrong version. Here that is harmless, because the
   salt did not change; the same mechanism is harmful for kallappam, where the ingredients
   did change.
2. **g03, "how much grated coconut goes into sanna".** The new kallappam-2025 intro chunk
   ranks #2, because **my own curated reformulation note** says it "replaces the grated
   coconut". Sanna's gold chunk drops to #4. The note I added for honesty created a BM25
   competitor.

**What this means for the plan:**
- This is an **integration-created taxonomy mode**: *superseded version outranks current*.
  It does not exist in the parts; it exists because the parts met a versioned corpus.
- **The fix belongs in the retrieval layer:** filter or down-rank `status: superseded`
  unless the question asks about an older version. It is scorable today, for free: the
  current-version hit@3 above is the before number.
- **I am not re-embedding or changing the retriever this week** (the brief's common mistake
  #1). Any fix is a filter on the metadata the CMS already carries.

## A candidate fix, scored offline: not shipped yet

Retrieve 25, drop `status: superseded` chunks unless the question asks about an older version
(old, original, previous, used to, 2024, superseded), then keep the top 3.

| | current-version hit@3 |
|---|---|
| retriever as shipped | 8/11 |
| **candidate filter** | **9/11** (g01 fixed) |

- **Still missed:** g03 (the competing reformulation note: a content problem, not a version
  problem) and g10 (a miss already in Week 4).
- **"Is kallappam nut free"** now retrieves only reformulated-2025 chunks.
- **a10's deliberate question about the original** still retrieves the original.

**It is held back on purpose.** The integrated before → after (allergen-unsafe answer rate)
needs a measured "before" run on the system as shipped. Wiring the filter in first would
leave nothing to compare against.
