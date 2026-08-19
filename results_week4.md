# Week 4 — Label the failures, then buy back hit-rate@3 with one change

Extends the Week 3 app. Same 6 recipe cards, same `recipes_structure_aware` collection, same
embedding model (`all-MiniLM-L6-v2`). **Exactly one retrieval change** was made: BM25 + reciprocal
rank fusion at k=60. The dense path (`search`) was not modified, so the before and after runs differ
by that alone. Diff in `retrieval_change_diff.md`.

**Headline: hit-rate@3 went 9/11 → 10/11, at a measured latency cost of ~0 ms** (BM25 adds 0.2–0.3 ms
to a dense embed that costs 170–930 ms depending on machine load). One of the two
original failures was fixed, one was not, and the reason the second survived is more interesting than
the fix.

---

## 1. The golden set (12 questions)

`golden_set.jsonl`. Ground truth is at **chunk_id** level, not recipe level, and every gold chunk was
verified to actually contain the answer before measuring.

| id | question | gold chunk_id | exact token | kind | source |
|---|---|---|---|---|---|
| g01 | how much rock salt in the idli batter | `idli-batter-05::structure::0` | 16g | quantity | authored |
| g02 | kallappam hydration percentage? | `kallappam-batter-02::structure::2` | 84% | quantity | authored |
| g03 | How much grated coconut goes into sanna? | `sanna-03::structure::0` | 150g | quantity | **demo session** |
| g04 | rice to dal ratio for kuzhi paniyaram | `kuzhi-paniyaram-batter-01::structure::1` | 3:1 | quantity | authored |
| g05 | what temp to bloom the yeast for kallappam | `kallappam-batter-02::structure::3` | 38C | temperature | authored |
| g06 | should i stir the paniyaram batter after it rises | `kuzhi-paniyaram-batter-01::structure::3` | — | — | authored |
| g07 | is moru ok if im allergic to milk | `moru-04::structure::5` | — | — | authored |
| g08 | how long does neeragaram ferment | `neeragaram-06::structure::2` | — | — | authored |
| g09 | fenugreek quantity for paniyaram batter | `kuzhi-paniyaram-batter-01::structure::0` | fenugreek | unusual-ingredient | authored |
| g10 | how much toddy for sanna | `sanna-03::structure::0` | toddy | unusual-ingredient | authored |
| g11 | how moru is made ? | `moru-04::structure::3` | — | — | **demo session** |
| g12 | where is the microsoft office present in US | *(none — not in corpus)* | — | — | **demo session** |

**7 of 12 carry an exact token** dense retrieval is structurally weak at (5 quantities, 1
temperature, 2 unusual ingredient names), above the required 4.

**Honest provenance.** Three questions (g03, g11, g12) are genuine — they were typed at the app
during a live demo, including the out-of-corpus one. The other nine are authored. They were written
to *probe* the exact-token weakness rather than to flatter the retriever, and they were written and
committed before any measurement: two of them fail at baseline.

**Two questions accept an alternative chunk.** `84%` genuinely appears in both
`kallappam-batter-02::structure::2` (the explicit "Hydration: 84%" line) and `::0` (the water table
row); "how moru is made" is answered across `moru-04::structure::3` and `::4`. Marking an equally
correct chunk as a miss would understate the retriever, so those two questions accept either. Every
other question has exactly one gold chunk.

**Scoring note.** g12 has no gold chunk, so it is excluded from the hit-rate denominator — hence
`/11`, not `/12`. It is scored in section 3 instead, on whether the app refuses.

---

## 2. Baseline hit-rate@3 — written down before any change

Dense retrieval only, `top_k = 3`.

| id | exact token | gold chunk | hit@3 | gold rank |
|---|---|---|---|---|
| g01 | 16g | `idli-batter-05::structure::0` | true | 3 |
| g02 | 84% | `kallappam-batter-02::structure::2` | true | 1 |
| g03 | 150g | `sanna-03::structure::0` | **false** | — |
| g04 | 3:1 | `kuzhi-paniyaram-batter-01::structure::1` | true | 1 |
| g05 | 38C | `kallappam-batter-02::structure::3` | true | 2 |
| g06 | — | `kuzhi-paniyaram-batter-01::structure::3` | true | 1 |
| g07 | — | `moru-04::structure::5` | true | 1 |
| g08 | — | `neeragaram-06::structure::2` | true | 1 |
| g09 | fenugreek | `kuzhi-paniyaram-batter-01::structure::0` | true | 3 |
| g10 | toddy | `sanna-03::structure::0` | **false** | — |
| g11 | — | `moru-04::structure::3` | true | 1 |
| g12 | — | *(not in corpus)* | excluded | — |

### **BASELINE: hit-rate@3 = 9/11**

Worth noting for the Week 3 write-up: **`top_k = 5` was hiding both of these.** At k=5 the sanna
table chunk was retrieved at rank 4 and both questions passed. Tightening to k=3 is what exposed
them.

---

## 3. Failure tally — R / G / Not-In-Corpus

| label | count | questions |
|---|---|---|
| **R** — retrieval fetched bad context | **2** | g03, g10 |
| **G** — model misused good context | **0 observed** | — |
| **Not-In-Corpus** | **1** | g12 |

**One line of evidence per label, from the inspection view:**

**g03 — R.** Gold `sanna-03::structure::0` was never returned; the top-3 were
`sanna-03::structure::2` (0.5205, method prose), `::4` (0.4834, allergen note) and `::1` (0.4699,
hydration line) — right recipe, wrong three chunks, and the ingredients table absent entirely.

**g10 — R.** Identical shape: gold `sanna-03::structure::0` absent, top-3 were `::1` (0.5439), `::2`
(0.4882), `::4` (0.4380).

**g12 — Not-In-Corpus.** No card contains any office location; the app returned exactly
`NOT_IN_CORPUS` when this was asked live during the demo, so it is a correct refusal rather than a
failure.

**How the 0 G was established, and its limit.** A G failure requires the gold chunk to be *in* the
top-3 and the answer still wrong, so it cannot be read off the retrieval metric. I ran generation on
the three retrieval-passing questions with the **weakest** gold rank — g01 (rank 3), g09 (rank 3),
g05 (rank 2) — on the reasoning that if the model were going to misuse good context, crowded context
is where it would happen. All three answered correctly with verified citations:

```
g01  expected 16g   correct=True   "The idli batter recipe calls for 16g (2%) of rock salt [idli-batter-05::structure::0]."
g05  expected 38C   correct=True   "Bloom the yeast at 38C [kallappam-batter-02::structure::3]."
g09  expected 6g    correct=True   "...6g (1% of the base rice weight) [kuzhi-paniyaram-batter-01::structure::0]."
```

g03 and g11 were also answered correctly during the live demo (cached transcripts), giving **5 of the
9 retrieval-passing questions confirmed non-G**. The remaining four were not generation-tested — the
Gemini free tier is 20 requests/day. So "0 G" means *no G failure observed in the cases most likely
to produce one*, not "G is impossible here".

### Why both R-failures are the same failure

Both point at one chunk — the sanna ingredients table:

```
# Sanna (sixteen steamed cakes)
Percentages are relative to the rice weight (500g = 100%).
## Ingredients
| Ingredient | Weight | Percentage of base |
|---|---|---|
| Idli rice, parboiled | 500g | 100% |
| Grated coconut | 150g | 30% |
| Toddy, or yeast slurry | 120g | 24% |
...
```

It is pipes, numbers and units with almost no prose. Its embedding carries weak semantic signal,
while the *method* chunk says "grind it with the grated coconut" in fluent English — so on "how much
grated coconut", the embedder prefers the chunk that reads like the question and skips the one that
holds the answer. This is the structural weakness the assignment describes, and it is a **lexical**
problem: `150g`, `120g` and `Toddy` are all literally present, just not semantically salient.

---

## 4. The one change, and why this one

**BM25 + RRF (k=60), not a different embedding model, and not a reranker.**

The tally says both failures are exact-token R-failures on a chunk whose content is literal values.
Swapping to a denser or better-trained embedding model is the one intervention that structurally
cannot fix this — the table's problem is not that its meaning is poorly encoded, it is that the
question's discriminating token (`toddy`, `150g`) is a *string* that appears in the document and
carries little distributional meaning. That is exactly the gap lexical retrieval exists to close, so
BM25 is the change the evidence points to. A cross-encoder rerank was the other option offered, but
it can only reorder what the first stage retrieved: for g03 the gold chunk was not in the dense top-3
at all, so a reranker over that candidate set has nothing to promote. It would also add real latency
per query, where BM25 over 33 chunks costs ~0.3 ms. Fusion is by **rank**, not score — cosine and
BM25 are on unrelated scales, which is precisely why RRF exists.

---

## 5. After the change

| id | exact token | before hit@3 | after hit@3 | verdict |
|---|---|---|---|---|
| g01 | 16g | true | true | already passing, untouched |
| g02 | 84% | true | true | already passing, untouched |
| g03 | 150g | **false** | **true** | **FIXED** (gold now rank 3) |
| g04 | 3:1 | true | true | already passing, untouched |
| g05 | 38C | true | true | already passing, untouched |
| g06 | — | true | true | already passing, untouched |
| g07 | — | true | true | already passing, untouched |
| g08 | — | true | true | already passing, untouched |
| g09 | fenugreek | true | true | already passing, untouched |
| g10 | toddy | **false** | **false** | **still broken** |
| g11 | — | true | true | already passing, untouched |
| g12 | — | excluded | excluded | not-in-corpus |

**No regressions.** Ranks also tightened where they were already passing: g01 3 → 1, g05 2 → 1,
g09 3 → 1. That is not scored by hit-rate@3, but it means less of the top-3 is wasted.

### Headline numbers

| metric | before (dense only) | after (bm25 + rrf) |
|---|---|---|
| **hit-rate@3** | **9/11** | **10/11** |
| **p50 latency per query, run A** | 931.2 ms | 924.0 ms |
| **p50 latency per query, run B** | 171.3 ms | 172.3 ms |

Two runs are reported because the absolute latency is machine-state dependent and the delta is not.
See below.

### The latency number needed a second look

A single sequential pass — measure all 12 on dense, then all 12 on hybrid — reported **176.3 ms →
958.2 ms**, a 5.4× penalty. That number is wrong, and reporting it would have killed a free change.
The baseline pass itself drifted from 161 ms on g01 to 953 ms on g08 with no change in code, so the
two retrievers were simply timed at different moments on a busy machine.

Re-measured properly — both retrievers timed **interleaved per question, 5 repeats**, run twice on
different machine load:

| retriever | run A p50 | run B p50 |
|---|---|---|
| dense only | 931.2 ms | 171.3 ms |
| **bm25 only** | **0.3 ms** | **0.2 ms** |
| bm25 + rrf | 924.0 ms | 172.3 ms |

Two things to read off this. **Within a run, hybrid and dense-only are indistinguishable** — hybrid
came out 7.2 ms faster in run A and 1.0 ms slower in run B, i.e. noise in both directions around a
zero delta. And **across runs the absolute figures move 5×** on identical code, which is the same
machine-load effect that faked the sequential result. So the only number worth quoting is the
component cost: **BM25 adds 0.2–0.3 ms**, against a dense embedding call of 171–931 ms.

**The honest price of this change is approximately zero.** The real latency problem in this app is
the local ONNX embed, roughly 600–4000× the lexical stage depending on load, and this work does not
touch it. Anyone reproducing these numbers should expect their own absolute values and check the
*delta*, not the milliseconds.

---

## 6. Which failures the change fixed, and which it did not touch

**Fixed — g03.** BM25 ranked the sanna table 1st on "How much grated coconut goes into sanna?"
because `Grated coconut` is a literal header-row match; fusion carried it to rank 3.

**Not touched — g10.** And the reason is specific, not "BM25 didn't help":

| ranking | gold's rank |
|---|---|
| dense | 4 |
| **BM25 alone** | **3** — would have been a hit |
| fused (RRF) | **4** |

BM25 *did* fix g10. **RRF then undid the fix.** The arithmetic:

| fused rank | chunk | dense rank | bm25 rank | RRF score |
|---|---|---|---|---|
| 1 | `sanna-03::structure::1` | 1 | 2 | 0.0164 + 0.0161 = 0.0325 |
| 2 | `sanna-03::structure::4` | 3 | 1 | 0.0159 + 0.0164 = 0.0323 |
| 3 | `sanna-03::structure::2` | 2 | 4 | 0.0161 + 0.0156 = 0.0318 |
| **4** | **`sanna-03::structure::0`** (gold) | 4 | 3 | 0.0156 + 0.0159 = **0.0315** |

The gold chunk is *second-best in both* rankings and top-2 in neither. RRF rewards consensus, and
consensus is exactly what a chunk with no first-place finish does not have. Three chunks each won one
list and so outranked it.

**Why BM25 could not discriminate here.** `toddy` appears in **four of the five** sanna chunks
(`::0` ×1, `::1` ×1, `::2` ×3, `::4` ×1), so it is not a rare term *within the recipe* and its IDF
advantage evaporates. Worse, the gold chunk is 47 tokens against a 48.4-token average while `::1` is
18 tokens, so BM25's length normalisation actively favours the short hydration line. Confirmation
that this is a query problem rather than an index problem: BM25 on `sanna 120g toddy` ranks the gold
chunk **1st (7.06)**. The token that would identify it — `120g` — is the answer, so the user asking
the question cannot supply it.

---

## 7. Shipping decision

**Ship BM25 + RRF.** hit-rate@3 **9/11 → 10/11** for a p50 cost of **+0.2 to 0.3 ms** on the
lexical stage — indistinguishable from zero against a 171–931 ms dense embed, and measured as noise
in both directions across two runs. A free +1 with zero regressions is worth shipping even though it only recovered
one of the two failures. It also promoted three already-passing questions from rank 3/2 to rank 1,
which reduces the chance of a future G failure from crowded context.

Two things this decision is *not*. It is not a fix for g10 — that needs either a chunker change
(fold the trailing summary line into the table chunk, so the ingredients table stops competing with
its own recipe's prose) or query-side term weighting, and I would measure that as a separate single
change rather than stacking it here. And it is not an endorsement of the team lead's proposal to swap
the embedding model: the tally says these were lexical exact-token failures, which a different
embedding is structurally the wrong tool for.

The honest caveat on the headline: **11 in-corpus questions means one question is worth 9
percentage points.** 9/11 → 10/11 is one question. I trust the direction because the mechanism is
visible in the ranks, not because the sample supports a claim about magnitude.

---

## 8. Bonus — MMR over the fused candidates

Greedy MMR over the fused candidate list, relevance normalised against the top RRF score, penalty =
max cosine similarity to what is already selected. Lambda swept once over four values. Diversity is
mean pairwise cosine *distance* across the top-3; "distinct recipes" counts how many different
recipes the three chunks come from.

| selector | hit-rate@3 | mean top-3 diversity | distinct recipes in top-3 |
|---|---|---|---|
| **bm25 + rrf (shipping)** | **10/11** | 0.348 | 1.27 |
| MMR λ=0.3 | 8/11 | 0.761 | 2.91 |
| MMR λ=0.5 | 8/11 | 0.692 | 2.82 |
| MMR λ=0.7 | 8/11 | 0.605 | 2.00 |
| MMR λ=0.9 | 10/11 | 0.406 | 1.27 |

**Would not ship.** Every lambda that meaningfully increases diversity costs two questions — 10/11
down to 8/11, an 18-point drop — and the one lambda that preserves hit-rate (0.9) buys almost
nothing: diversity 0.348 → 0.406 with distinct recipes unchanged at 1.27. There is no setting on this
sweep that trades favourably.

The reason is that MMR's premise does not hold for this corpus. MMR assumes near-duplicate results
waste slots, which is true when three chunks are three variations of the same base dough. Here every
question targets exactly one recipe, and the correct answer is *concentrated* in that recipe's
chunks — so spending a top-3 slot on a different recipe is spending it on a guaranteed miss. Forcing
2.91 distinct recipes into three slots means at most one slot remains for the recipe actually asked
about. This is the failure mode the brief warns about, and it shows up as a number: **MMR pushed the
correct chunk out of the top-3 on two questions in the name of variety.**

---

## Files

| file | what it is |
|---|---|
| `golden_set.jsonl` | 12 questions with chunk-level ground truth |
| `evaluate_retrieval.py` | hit-rate@3, the inspection view, interleaved latency |
| `mmr_bonus.py` | the bonus lambda sweep |
| `retrieval_change_diff.md` | the diff of the one retrieval change |
| `mmr_bonus.json` | bonus results |
| `recipe_rag.py` | `search_bm25`, `search_hybrid_rrf` added; `search` untouched |

Reproduce: `python evaluate_retrieval.py` then `python mmr_bonus.py`. Both are free and local — no
API calls. Only the three G-probes in section 3 used the API.
