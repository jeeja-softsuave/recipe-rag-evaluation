# Code diff — the ONE retrieval change

BM25 + reciprocal rank fusion (k=60) added alongside the existing dense retriever.
The dense path (`search`) is untouched, so the before/after runs differ by exactly this.

```diff
diff --git a/recipe_rag.py b/recipe_rag.py
index 85c9d17..8c34cea 100644
--- a/recipe_rag.py
+++ b/recipe_rag.py
@@ -2,6 +2,7 @@
 
 from __future__ import annotations
 
+import math
 import re
 import time
 from pathlib import Path
@@ -33,6 +34,12 @@ TABLE_ROWS_PER_CHUNK = 6
 METHOD_SENTENCES_PER_CHUNK = 4
 DIETARY_TAG_PREFIX = "tag_"
 SENTENCE_SPLIT_PATTERN = r"(?<=[.;])\s+"
+BM25_K1 = 1.5
+BM25_B = 0.75
+RRF_K = 60
+HYBRID_CANDIDATE_DEPTH = 25
+# Keeps "16g", "84%", "3:1" and "38c" as single tokens instead of splitting them apart.
+TOKEN_PATTERN = r"\d+(?:[.:]\d+)?%?[a-z]*|[a-z]+"
 GEMINI_MODEL = "gemini-3.6-flash"
 GEMINI_THINKING_LEVEL = "low"
 GEMINI_MAX_ATTEMPTS = 4
@@ -324,6 +331,106 @@ def search_with_dietary_filter(
     return results
 
 
+def _tokenize(text: str) -> list[str]:
+    """Lower-case and split text into lexical tokens, keeping quantities intact."""
+    return re.findall(TOKEN_PATTERN, text.lower())
+
+
+_CORPUS_CACHE: dict[str, dict[str, Any]] = {}
+
+
+def _load_corpus(collection: Collection) -> dict[str, Any]:
+    """Read every chunk once and cache the tokenised corpus for lexical scoring."""
+    if collection.name in _CORPUS_CACHE:
+        return _CORPUS_CACHE[collection.name]
+    stored = collection.get(include=["documents", "metadatas"])
+    tokenised = [_tokenize(doc) for doc in stored["documents"]]
+    document_frequency: dict[str, int] = {}
+    for tokens in tokenised:
+        for token in set(tokens):
+            document_frequency[token] = document_frequency.get(token, 0) + 1
+    corpus = {
+        "ids": stored["ids"],
+        "documents": stored["documents"],
+        "metadatas": stored["metadatas"],
+        "tokenised": tokenised,
+        "document_frequency": document_frequency,
+        "average_length": sum(len(t) for t in tokenised) / max(len(tokenised), 1),
+    }
+    _CORPUS_CACHE[collection.name] = corpus
+    return corpus
+
+
+def _as_result(corpus: dict[str, Any], index: int, rank: int, score: float) -> dict[str, Any]:
+    """Shape one corpus entry like a search() result."""
+    metadata = corpus["metadatas"][index]
+    return {
+        "rank": rank,
+        "chunk_id": corpus["ids"][index],
+        "text": corpus["documents"][index],
+        "score": round(score, 4),
+        "recipe_id": metadata.get("recipe_id", ""),
+        "section": metadata.get("section", ""),
+        "source_file": metadata.get("source_file", ""),
+        "cuisine": metadata.get("cuisine", ""),
+        "dietary_tags": metadata.get("dietary_tags", ""),
+    }
+
+
+def search_bm25(
+    collection: Collection, query: str, top_k: int = TOP_K
+) -> list[dict[str, Any]]:
+    """Return the top_k chunks by BM25 lexical relevance, best first."""
+    corpus = _load_corpus(collection)
+    total_documents = len(corpus["ids"])
+    query_tokens = _tokenize(query)
+    scored: list[tuple[float, int]] = []
+    for index, tokens in enumerate(corpus["tokenised"]):
+        length = len(tokens)
+        score = 0.0
+        for token in query_tokens:
+            frequency = tokens.count(token)
+            if not frequency:
+                continue
+            document_frequency = corpus["document_frequency"].get(token, 0)
+            idf = math.log(
+                1 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5)
+            )
+            denominator = frequency + BM25_K1 * (
+                1 - BM25_B + BM25_B * length / max(corpus["average_length"], 1e-9)
+            )
+            score += idf * frequency * (BM25_K1 + 1) / denominator
+        if score > 0:
+            scored.append((score, index))
+    scored.sort(key=lambda pair: (-pair[0], corpus["ids"][pair[1]]))
+    return [
+        _as_result(corpus, index, rank, score)
+        for rank, (score, index) in enumerate(scored[:top_k], start=1)
+    ]
+
+
+def search_hybrid_rrf(
+    collection: Collection, query: str, top_k: int = TOP_K
+) -> list[dict[str, Any]]:
+    """Fuse dense and BM25 rankings with reciprocal rank fusion, best first."""
+    dense = search(collection, query, HYBRID_CANDIDATE_DEPTH)
+    lexical = search_bm25(collection, query, HYBRID_CANDIDATE_DEPTH)
+    # RRF fuses RANKS, never raw scores: cosine and BM25 are not on a shared scale.
+    fused: dict[str, float] = {}
+    for ranking in (dense, lexical):
+        for hit in ranking:
+            fused[hit["chunk_id"]] = fused.get(hit["chunk_id"], 0.0) + 1.0 / (
+                RRF_K + hit["rank"]
+            )
+    corpus = _load_corpus(collection)
+    position_of = {chunk_id: index for index, chunk_id in enumerate(corpus["ids"])}
+    ordered = sorted(fused.items(), key=lambda pair: (-pair[1], pair[0]))
+    return [
+        _as_result(corpus, position_of[chunk_id], rank, score)
+        for rank, (chunk_id, score) in enumerate(ordered[:top_k], start=1)
+    ]
+
+
 def build_generation_prompt(question: str, contexts: list[dict[str, Any]]) -> str:
     """Render retrieved chunks and the question into the user prompt."""
     blocks = [f"[{chunk['chunk_id']}]\n{chunk['text']}" for chunk in contexts]
@@ -399,9 +506,10 @@ def answer_with_citations(
     question: str,
     generate: Any = _gemini_generate,
     top_k: int = TOP_K,
+    retriever: Any = search_hybrid_rrf,
 ) -> dict[str, Any]:
     """Answer a question from retrieved context and verify every citation."""
-    contexts = search(collection, question, top_k)
+    contexts = retriever(collection, question, top_k)
     user_prompt = build_generation_prompt(question, contexts)
     answer = generate(SYSTEM_PROMPT, user_prompt)
     refused = answer.strip() == REFUSAL_TEXT
```
