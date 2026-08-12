# Code diff — the second chunker and the metadata fields

Required by the submission checklist. This is the real diff between the first working
version (baseline chunker only, minimal metadata) and the version that added the
structure-aware chunker plus the full metadata set.

```diff
diff --git a/recipe_rag.py b/recipe_rag.py
index bfb13f2..dd7acb1 100644
--- a/recipe_rag.py
+++ b/recipe_rag.py
@@ -2,6 +2,7 @@
 
 from __future__ import annotations
 
+import re
 from pathlib import Path
 from typing import Any
 
@@ -15,11 +16,18 @@ CHROMA_DIR = str(Path(__file__).parent / "chroma_db")
 CARD_GLOB = "card-*.md"
 TOP_K = 5
 BASELINE_COLLECTION = "recipes_baseline"
+STRUCTURE_AWARE_COLLECTION = "recipes_structure_aware"
 EMBEDDING_MODEL = "all-MiniLM-L6-v2"
 BASELINE_CHUNK_SIZE = 400
 BASELINE_CHUNK_OVERLAP = 80
 FRONT_MATTER_FENCE = "---"
 SECTION_HEADING_PREFIX = "## "
+INGREDIENTS_SECTION = "ingredients"
+METHOD_SECTION = "method"
+TABLE_ROWS_PER_CHUNK = 6
+METHOD_SENTENCES_PER_CHUNK = 4
+DIETARY_TAG_PREFIX = "tag_"
+SENTENCE_SPLIT_PATTERN = r"(?<=[.;])\s+"
 
 
 def _embedding_function() -> embedding_functions.EmbeddingFunction:
@@ -79,6 +87,8 @@ def load_recipe_cards(cards_dir: Path = RECIPE_CARDS_DIR) -> list[dict[str, Any]
                 "source_file": path.name,
                 "recipe_id": front.get("recipe_id", ""),
                 "title": front.get("title", title_line),
+                "cuisine": front.get("cuisine", ""),
+                "dietary_tags": front.get("dietary_tags", ""),
                 "body": body,
                 "sections": _split_sections(body),
             }
@@ -88,14 +98,31 @@ def load_recipe_cards(cards_dir: Path = RECIPE_CARDS_DIR) -> list[dict[str, Any]
     return cards
 
 
+def parse_dietary_tags(dietary_tags: str) -> list[str]:
+    """Split a comma-separated dietary_tags string into clean tags."""
+    return [tag.strip() for tag in dietary_tags.split(",") if tag.strip()]
+
+
+def _dietary_tag_flags(dietary_tags: str) -> dict[str, bool]:
+    """Expand dietary tags into one boolean metadata flag each, for filtering."""
+    return {
+        f"{DIETARY_TAG_PREFIX}{tag.replace('-', '_')}": True
+        for tag in parse_dietary_tags(dietary_tags)
+    }
+
+
 def _chunk_metadata(card: dict[str, Any], section: str, chunk_id: str) -> dict[str, Any]:
     """Build the metadata dict carried by every chunk."""
-    return {
+    metadata: dict[str, Any] = {
         "chunk_id": chunk_id,
         "source_file": card["source_file"],
         "recipe_id": card["recipe_id"],
+        "cuisine": card["cuisine"],
+        "dietary_tags": card["dietary_tags"],
         "section": section,
     }
+    metadata.update(_dietary_tag_flags(card["dietary_tags"]))
+    return metadata
 
 
 def chunk_baseline(card: dict[str, Any]) -> list[dict[str, Any]]:
@@ -121,6 +148,74 @@ def chunk_baseline(card: dict[str, Any]) -> list[dict[str, Any]]:
     return chunks
 
 
+def _split_table(section_text: str) -> tuple[list[str], list[str], list[str]]:
+    """Split an ingredients section into table header lines, row lines and loose prose."""
+    header: list[str] = []
+    rows: list[str] = []
+    prose: list[str] = []
+    for line in section_text.splitlines():
+        stripped = line.strip()
+        if not stripped:
+            continue
+        if stripped.startswith("|"):
+            if len(header) < 2:
+                header.append(stripped)
+            else:
+                rows.append(stripped)
+        else:
+            prose.append(stripped)
+    return header, rows, prose
+
+
+def chunk_structure_aware(card: dict[str, Any]) -> list[dict[str, Any]]:
+    """Chunk a card so ingredient rows keep their table header and recipe title."""
+    chunks: list[dict[str, Any]] = []
+    sections = card["sections"]
+    title = f"# {card['title']}"
+    intro = sections.get("intro", "")
+    index = 0
+
+    def add(text: str, section: str) -> None:
+        nonlocal index
+        chunk_id = f"{card['recipe_id']}::structure::{index}"
+        chunks.append(
+            {
+                "chunk_id": chunk_id,
+                "text": text,
+                "metadata": _chunk_metadata(card, section, chunk_id),
+            }
+        )
+        index += 1
+
+    # Ingredient rows travel with the title, the percentage basis and the table header.
+    ingredients = sections.get(INGREDIENTS_SECTION, "")
+    if ingredients:
+        header, rows, prose = _split_table(ingredients)
+        preamble = "\n".join(part for part in (title, intro, "## Ingredients", *header) if part)
+        for start in range(0, len(rows), TABLE_ROWS_PER_CHUNK):
+            batch = rows[start : start + TABLE_ROWS_PER_CHUNK]
+            add("\n".join([preamble, *batch]), INGREDIENTS_SECTION)
+        if prose:
+            add("\n".join([title, "## Ingredients", *prose]), INGREDIENTS_SECTION)
+
+    # Method prose is kept in its own chunks, grouped a few sentences at a time.
+    method = sections.get(METHOD_SECTION, "")
+    if method:
+        sentences = [s.strip() for s in re.split(SENTENCE_SPLIT_PATTERN, method) if s.strip()]
+        for start in range(0, len(sentences), METHOD_SENTENCES_PER_CHUNK):
+            batch = sentences[start : start + METHOD_SENTENCES_PER_CHUNK]
+            add("\n".join([title, "## Method", " ".join(batch)]), METHOD_SECTION)
+
+    # Any remaining section (the allergen note) becomes one titled chunk.
+    for name, text in sections.items():
+        if name in {"intro", INGREDIENTS_SECTION, METHOD_SECTION}:
+            continue
+        heading = name.replace("_", " ").title()
+        add("\n".join([title, f"## {heading}", text]), name)
+
+    return chunks
+
+
 def build_index(collection_name: str, chunks: list[dict[str, Any]]) -> Collection:
     """Create a fresh collection and upsert chunks after validating metadata."""
     for chunk in chunks:
@@ -165,6 +260,8 @@ def search(collection: Collection, query: str, top_k: int = TOP_K) -> list[dict[
                 "recipe_id": metadata.get("recipe_id", ""),
                 "section": metadata.get("section", ""),
                 "source_file": metadata.get("source_file", ""),
+                "cuisine": metadata.get("cuisine", ""),
+                "dietary_tags": metadata.get("dietary_tags", ""),
             }
         )
     return results
```

## Follow-up fix in the same file

The intro block still carried the H1 line, so the recipe title was duplicated in every
table chunk:

```diff
+    # The intro block still holds the H1 line; drop it so the title is not repeated.
+    intro = "\n".join(
+        line
+        for line in sections.get("intro", "").splitlines()
+        if not line.startswith("# ")
+    ).strip()
     index = 0
 
     def add(text: str, section: str) -> None:
```
