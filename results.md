# Fermentation chapter — chunking experiment results

**Only the 6 new recipe cards in `data/recipe_cards/` were indexed.** No pre-existing corpus was
touched or re-indexed. Both collections (`recipes_baseline` and `recipes_structure_aware`) were built
from exactly these six files and nothing else:

```
card-01-kuzhi-paniyaram-batter.md   card-04-moru.md
card-02-kallappam-batter.md         card-05-idli-batter.md
card-03-sanna.md                    card-06-neeragaram.md
```

Same embedding model for both (`all-MiniLM-L6-v2`, Chroma's local ONNX default), same `top_k = 5`,
cosine distance. **The chunker is the only variable between the two collections.** 30 baseline chunks
vs 33 structure-aware chunks.

### Two things to know before reading the numbers

1. **The cards are authored, not supplied.** The working directory was empty when this started — no
   existing RAG app, no `data/recipe_cards/`, no prior chunker, no vector store installed. The six
   cards were written for this exercise in the required format (front-matter + ingredient table +
   method prose + allergen note). Every number below is a real measurement, but it measures *this*
   corpus. Drop different cards into `data/recipe_cards/` and rerun `run_retrieval.py` — no code
   changes needed. Percentages are true baker's percentages for the four rice batters (rice = 100%);
   moru and neeragaram base theirs on curd and cooked rice, stated in each card's intro line.
2. **Generation (sections 4, 5 and 8) is pending a quota reset.** Retrieval is fully measured and
   reproducible right now. The generation half needs 10 live Gemini calls against a free-tier quota
   of 20 requests, which is spent. Those sections state what will be produced rather than showing
   output from a previous corpus.

---

## 1. The 8 questions, with known-correct recipe and section

Written from the cards before any search was run (`eval_questions.json`).

| id | question | expected_recipe_id | expected_section | needs_table_row | known-correct answer |
|---|---|---|---|---|---|
| q1 | How much rock salt goes into the idli batter? | idli-batter-05 | ingredients | true | 16g (2%) |
| q2 | What hydration percentage is the kallappam batter? | kallappam-batter-02 | ingredients | true | 84% (420g water / 500g rice) |
| q3 | How much grated coconut goes into sanna? | sanna-03 | ingredients | true | 150g (30%) |
| q4 | What is the rice to dal ratio for kuzhi paniyaram batter? | kuzhi-paniyaram-batter-01 | ingredients | true | 3:1 (600g rice / 200g dal) |
| q5 | At what temperature should the yeast be bloomed for kallappam? | kallappam-batter-02 | method | false | 38C — hotter kills the yeast |
| q6 | Should the risen kuzhi paniyaram batter be stirred before cooking? | kuzhi-paniyaram-batter-01 | method | false | No — stirring knocks out the gas |
| q7 | Is moru safe for someone with a milk protein allergy? | moru-04 | allergen_note | false | No — contains dairy; not lactose-free either |
| q8 | How long does neeragaram ferment for? | neeragaram-06 | method | false | 6 to 8 hours at ambient temperature |

4 of 8 need an exact table row (q1–q4), above the required 3.

## 2. hit_in_top_5, both chunkers

| question_id | expected_recipe_id | baseline_hit | structure_aware_hit |
|---|---|---|---|
| q1 | idli-batter-05 | true | true |
| q2 | kallappam-batter-02 | true | true |
| q3 | sanna-03 | true | true |
| q4 | kuzhi-paniyaram-batter-01 | true | true |
| q5 | kallappam-batter-02 | true | true |
| q6 | kuzhi-paniyaram-batter-01 | true | true |
| q7 | moru-04 | true | true |
| q8 | neeragaram-06 | true | true |

**baseline: hit_in_top_5 = 8 out of 8**
**structure_aware: hit_in_top_5 = 8 out of 8**

This metric is saturated and does not discriminate. With 6 cards and 5 slots, recall of the right
*recipe* is nearly free — a top-5 over 30–33 chunks drawn from only six documents will almost always
include one. Reporting 8/8 vs 8/8 as "tied" would be the wrong read; the metric is too easy at this
corpus size. Two harder measures separate them sharply.

### 2a. Top-1 correctness — the number that moved

| chunker | questions where top-1 was the **wrong recipe** | mean correct chunks in top-5 |
|---|---|---|
| baseline | **4 of 8** (q1, q3, q7, q8) | 2.5 / 5 |
| structure_aware | **0 of 8** | 3.9 / 5 |

| qid | expected | baseline's top-1 | rank of first correct |
|---|---|---|---|
| q1 | idli-batter-05 | neeragaram-06 | 2 |
| q3 | sanna-03 | kallappam-batter-02 | 4 |
| q7 | moru-04 | kuzhi-paniyaram-batter-01 | 2 |
| q8 | neeragaram-06 | kuzhi-paniyaram-batter-01 | 2 |

Half of baseline's top-1 answers are the wrong dish. Structure-aware never once put the wrong recipe
first. This corpus is what exposes it: four of the six cards are fermented rice batters whose method
prose reads almost identically ("soak 4 hours", "grind with ice-cold water", "ferment N hours at
30C"), and the only text that distinguishes them is the recipe title.

### 2b. Does the retrieved text carry the answer, usably?

`value_hit` = some top-5 chunk literally contains the answer value. `usable_hit` = that chunk also
carries the parent recipe title, and for table questions the table header too — i.e. the number
arrives interpretable rather than orphaned. Measured on chunk *text*, not on labels.

| qid | needs_table_row | baseline value | baseline usable | struct value | struct usable |
|---|---|---|---|---|---|
| q1 | true | true | true | true | true |
| q2 | true | true | true | true | true |
| q3 | true | true | true | true | true |
| q4 | true | true | true | true | **false** |
| q5 | false | true | **false** | true | true |
| q6 | false | true | **false** | true | true |
| q7 | false | true | **false** | true | true |
| q8 | false | true | **false** | true | true |

| chunker | value_hit | usable_hit | usable on table questions |
|---|---|---|---|
| baseline | 8/8 | **4/8** | 4/4 |
| structure_aware | 8/8 | **7/8** | 3/4 |

Baseline finds the value every time but loses the parent title on all four prose questions — a
400-character window sliced out of a method paragraph has no `# Title` line, so the text does not say
which batter it belongs to. That is the same defect that produces the four wrong top-1 answers above:
the chunks are not just hard to attribute after retrieval, they are hard to *rank* correctly during
it.

Structure-aware's single miss (q4) is a genuine defect in my chunker, diagnosed in section 7.

A methodology note in the interest of not overstating precision: the first run of this table showed
`value_hit = false` for q8 on both chunkers. That was my answer key, not retrieval — the card wraps
"6 to 8\nhours" across a source line, so the literal substring never matched. `analyze.py` now
collapses whitespace on both sides before comparing. A metric that silently fails on line wrapping is
worth fixing before it flatters or damns a chunker by accident.

Against over-reading all of this: 8 questions over 6 cards means one question is worth 12.5%. The
4-of-8 top-1 gap is a mechanism you can point at in the chunk text, not a statistical result, and
that is why I trust it. Nothing here would survive being quoted as a benchmark.

## 3. Unfiltered vs filtered (dietary_tags)

Query: `how much curd do I need` · filter: `dietary_tags` contains `vegan` ·
collection: `recipes_structure_aware` · top_k = 5

**Unfiltered**

| rank | chunk_id | recipe_id | dietary_tags | score |
|---|---|---|---|---|
| 1 | moru-04::structure::2 | moru-04 | vegetarian, gluten-free, contains-dairy | 0.3227 |
| 2 | moru-04::structure::3 | moru-04 | vegetarian, gluten-free, contains-dairy | 0.2957 |
| 3 | moru-04::structure::0 | moru-04 | vegetarian, gluten-free, contains-dairy | 0.2814 |
| 4 | moru-04::structure::1 | moru-04 | vegetarian, gluten-free, contains-dairy | 0.2656 |
| 5 | sanna-03::structure::1 | sanna-03 | vegan, gluten-free | 0.2069 |

**Filtered (`vegan`)**

| rank | chunk_id | recipe_id | dietary_tags | score |
|---|---|---|---|---|
| 1 | sanna-03::structure::1 | sanna-03 | vegan, gluten-free | 0.2069 |
| 2 | sanna-03::structure::2 | sanna-03 | vegan, gluten-free | 0.1849 |
| 3 | sanna-03::structure::0 | sanna-03 | vegan, gluten-free | 0.1736 |
| 4 | kuzhi-paniyaram-batter-01::structure::1 | kuzhi-paniyaram-batter-01 | vegan, gluten-free | 0.1714 |
| 5 | kallappam-batter-02::structure::2 | kallappam-batter-02 | vegan, gluten-free | 0.1554 |

**top-1 changed: yes.** `moru-04::structure::2` (0.3227, contains-dairy) is replaced by
`sanna-03::structure::1` (0.2069, vegan). The four dairy chunks that occupied ranks 1–4 are gone
entirely. Scores are unchanged for surviving chunks — the filter is a pre-query restriction, not a
re-scoring — so the new top-1 has a *lower* score than the old one. That is the point: a vegan user
asking about curd quantities should not be handed a buttermilk recipe just because it is the closest
semantic match.

Implementation note: Chroma metadata values must be scalars, so `dietary_tags` is stored as the
original comma string *and* expanded into one boolean flag per tag (`tag_vegan`, `tag_contains_dairy`,
…). `search_with_dietary_filter` filters on the flag, because Chroma cannot substring-match a metadata
string.

## 4. Three cited answers — PENDING QUOTA RESET

Not yet run against this corpus. The Gemini free tier allows 20 requests and the quota is spent;
`run_generation.py` needs 6 of them. The three answerable questions are fixed in that script — the
idli batter's rock salt, sanna's grated coconut, and kallappam's yeast bloom temperature — and the
system prompt is fixed too:

```
Answer only from the provided context. If the context does not contain the answer, reply exactly: NOT_IN_CORPUS
Cite the chunk you used after every claim, in square brackets, like [chunk_id]. Every sentence that states a fact must carry at least one citation.
```

`verify_citations` checks each `[chunk_id]` exists **and** that the chunk's text contains the claimed
number. That verifier is tested and passing right now against this corpus — `tests.py`:

| case | result |
|---|---|
| correct value `16g` cited to the idli table chunk | ok=True |
| wrong value `35g` cited to the same chunk | ok=False, missing `35g` |
| correct value `16g` cited to the moru chunk instead | ok=False, missing `16g` |
| invented id `does-not-exist::structure::99` | ok=False, exists=False |
| correct percent `84%` | ok=True |
| wrong percent `62%` | ok=False, missing `62%` |
| decimal percent `2.3%` | ok=True |
| wrong ratio `1:9` | ok=False, missing `1:9` |

Two known limits, worth stating before the transcripts exist. Sentences with no numeric value verify
trivially (`claimed=(none) → ok=True`), so a prose claim is confirmed only to *cite* a real chunk, not
to be true of it. And an earlier `VALUE_PATTERN` ended in `\b` after `%`, which never matches, so
**every percentage claim silently verified as empty** until it was fixed — `all_citations_ok = True`
means "every number was checked and every cited chunk exists", nothing more.

On an earlier corpus, verification also proved **unstable across runs**: the same pipeline returned
`all_citations_ok = False` on one answerable question on a rerun, because the model rephrased and
attached a value to a chunk that did not contain it. Expect the same here. One green run is a sample,
not a property.

## 5. Three refusals — PENDING QUOTA RESET

The three out-of-corpus questions are fixed in `run_generation.py`: calories per serving, protein and
fat macros, and glycemic index — none of which appears on any card. Each will retrieve five real
chunks from the right recipe, so the context will be on-topic and simply contain no nutrition data.
`refused` is computed by exact match against `NOT_IN_CORPUS`, not by reading prose, so it is a boolean
rather than a judgement.

On an earlier corpus this returned 3/3 exact refusals from the live model. That is a smoke test, not a
refusal rate — all three questions are nutrition-shaped, so they probe one kind of absence. A harder
set would ask things that *sound* like they are on these cards but are not: a rice-to-dal ratio for
sanna, a bloom temperature for the idli batter.

## 6. Which chunker ships, and why

**`chunk_structure_aware` ships**, and on this corpus the case is no longer subtle. Both chunkers
scored 8/8 on `hit_in_top_5`, which at six cards measures almost nothing — but baseline put the
**wrong dish first on half the questions** (4 of 8) while structure-aware never did, and baseline lost
the parent recipe title on every prose question. The cause is one thing: four of these six cards are
fermented rice batters whose method prose is nearly interchangeable, so the recipe title is the only
disambiguating text in the document. A fixed 400-character window starting mid-paragraph contains no
title, so it is both unrankable and unattributable — the embedding has nothing to prefer sanna's
coconut over kallappam's, and the generator receiving that chunk cannot tell which batter it is
reading. Structure-aware stamps the title on every chunk, which fixes both at once, and puts 3.9 of
its 5 slots on the right recipe against baseline's 2.5. The cost is real and I would not hide it:
separating table from method means a procedural question retrieves method chunks with no numbers in
them, and it currently splits a table's trailing summary line away from the table header, which is
q4 and the one case where it is worse than baseline. Both are fixable inside the chunker; baseline's
missing-title problem is not fixable without becoming structure-aware. Ship structure-aware, then
fold trailing summary prose into the last table chunk, and attach a short method excerpt to ingredient
chunks so procedural questions still get quantities.

## 7. One retrieval that embarrassed us, and the diagnosis

**q3, baseline collection.** "How much grated coconut goes into sanna?" Correct answer: **150g (30%)**,
in the sanna ingredients table.

| rank | chunk_id | score | has `150g` | has title "Sanna" |
|---|---|---|---|---|
| 1 | kallappam-batter-02::baseline::1 | 0.4950 | no | **no** |
| 2 | moru-04::baseline::1 | 0.4825 | no | **no** |
| 3 | kallappam-batter-02::baseline::2 | 0.4804 | no | **no** |
| 4 | sanna-03::baseline::0 | 0.4708 | **yes** | **yes** |
| 5 | sanna-03::baseline::3 | 0.4604 | no | no |

The top three results are the wrong recipe, and **not one of them carries a title**. Ranks 1 and 3 are
kallappam — the *other* coconut-containing fermented rice batter. The correct chunk finally appears at
rank 4, and hit@5 duly records this question as a success.

Structure-aware on the same question returns sanna at ranks 1–4, every chunk titled, with the `150g`
row at rank 4.

**Diagnosis.** This is not an embedding failure and not a missing document — it is a chunk-boundary
failure. Kallappam and sanna are both ground-rice-and-coconut ferments, and once you strip the title
their ingredient windows are near-duplicates: "grated coconut", "cooked rice", "water for grinding",
similar gram weights. The title is the *only* token that separates them, and baseline's fixed windows
start mid-document, so three of its five slots went to a dish the user did not ask about with nothing
in the text to reveal the error. A model handed rank 1 would confidently report kallappam's 100g of
coconut as sanna's, cite a real chunk id, and be wrong — and the citation would resolve.

The scores make it worse: 0.4950 for the wrong recipe against 0.4708 for the right one. The ranking is
not merely unlucky, it is *confidently* inverted, and nothing in the retrieved text would let a
downstream check catch it.

**Secondary embarrassment, structure-aware, q4.** The rice-to-dal ratio `3:1` lives in the summary
line under the table, which my chunker emits as its own chunk carrying the title but **not** the table
header — so the value arrives without the 600g and 200g that produce it. It is the one question where
structure-aware is worse than baseline, and the cause is my own code treating a trailing summary as
loose prose. The one-line fix is to append trailing summary prose to the final table chunk. I left it
unfixed rather than special-case the test.

## 8. Bonus — PENDING QUOTA RESET

`bonus_generate.py` asks the same recipe two questions — one narrow ("how much X"), one procedural
("how do I make it") — against both collections, and reports whether a method-only caveat was
retrieved and whether it reached the answer.

On an earlier corpus this **refuted** the predicted effect: asked narrowly, both chunkers produced
identical one-line answers and neither included the method caveat, even where baseline had retrieved
it, so the completeness gap was latent in retrieval but never realized in the answer. Asked
procedurally, both included the caveat and the real difference ran the *other* way — structure-aware
returned a complete procedure with no quantities, because its method chunks contain no numbers. That
will be re-tested here rather than assumed.

---

## The week-level task: "ask my documents"

This set is the measurement extension; the week's own task is *"let a user ask a question, and answer
using only those documents — with a link to the source. If the answer isn't in the documents, it
should say so instead of inventing one."* That maps to `ask.py`:

| Week-level clause | Where |
|---|---|
| "let a user ask a question" | `ask.py` prompt — pick one of the 8 known questions by number, or type any question |
| "answer using only those documents" | `SYSTEM_PROMPT` — answer only from provided context; the model sees nothing but the retrieved chunks |
| "with a link to the source" | every result and every citation prints `data/recipe_cards/<card>.md`, resolved from the chunk's `source_file` metadata |
| "say so instead of inventing one" | the forced `NOT_IN_CORPUS` reply, printed as *"refused: True (answer is not in these documents)"* |

Because `ask.py` knows the expected recipe, section and value for the 8 eval questions, it marks hits
inline (`*` for the expected recipe, `<- contains 150g` for chunks that hold the answer) and shows
both chunkers side by side — so section 2's numbers can be reproduced interactively rather than taken
on trust. Question 3 is the one to demo: baseline's top-1 is the wrong batter. Retrieval is free and
local; typing a question answers it, and adding `!r` compares both chunkers without spending an API
call. Answers are cached locally so a repeated question replays for free, labelled `replayed from
cache` — the citation check still re-runs against Chroma every time either way.

## Files

| file | what it is |
|---|---|
| `recipe_rag.py` | constants + the 8 named functions + the Gemini generator |
| `run_retrieval.py` | builds both indexes, runs the 8 questions, dietary filter, writes `search_dump.md` |
| `run_generation.py` | the 6 transcripts + citation verification |
| `analyze.py` | evidence behind the chunker choice: top-1 correctness, usable-answer grading |
| `tests.py` | guards: the `source_file` refusal and the citation-verifier negative controls |
| `bonus_generate.py` | the bonus comparison |
| `ask.py` | the interactive "ask my documents" console (week-level task) |
| `eval_questions.json`, `answer_keys.json` | the 8 questions and their known-correct values |
| `search_dump.md` | every raw top-5 list for all 8 questions, both chunkers, with chunk text |
| `chunker_diff.md` | the code diff adding the second chunker and the metadata fields |

Rerun order: `run_retrieval.py` → `analyze.py` → `tests.py` → `run_generation.py` → `bonus_generate.py`.
The first three are free and local. The last two make **10 live API calls**, against a Gemini
free-tier quota of **20 requests**.
