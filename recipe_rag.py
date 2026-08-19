"""Recipe-card RAG over the new fermentation cards only."""

from __future__ import annotations

import math
import re
import time
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# Read .env so GEMINI_API_KEY is available without exporting it into the shell.
load_dotenv()

# --- Configuration: every tunable value lives here, none inline below. ---
RECIPE_CARDS_DIR = Path(__file__).parent / "data" / "recipe_cards"
CHROMA_DIR = str(Path(__file__).parent / "chroma_db")
CARD_GLOB = "card-*.md"
TOP_K = 5
BASELINE_COLLECTION = "recipes_baseline"
STRUCTURE_AWARE_COLLECTION = "recipes_structure_aware"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
BASELINE_CHUNK_SIZE = 400
BASELINE_CHUNK_OVERLAP = 80
FRONT_MATTER_FENCE = "---"
SECTION_HEADING_PREFIX = "## "
INGREDIENTS_SECTION = "ingredients"
METHOD_SECTION = "method"
TABLE_ROWS_PER_CHUNK = 6
METHOD_SENTENCES_PER_CHUNK = 4
DIETARY_TAG_PREFIX = "tag_"
SENTENCE_SPLIT_PATTERN = r"(?<=[.;])\s+"
BM25_K1 = 1.5
BM25_B = 0.75
RRF_K = 60
EPSILON = 1e-9
HYBRID_CANDIDATE_DEPTH = 25
# Keeps "16g", "84%", "3:1" and "38c" as single tokens instead of splitting them apart.
TOKEN_PATTERN = r"\d+(?:[.:]\d+)?%?[a-z]*|[a-z]+"
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_THINKING_LEVEL = "low"
GEMINI_MAX_ATTEMPTS = 4
GEMINI_DEFAULT_RETRY_SECONDS = 30.0
RETRY_DELAY_PATTERN = r"retry in ([\d.]+)s"
REFUSAL_TEXT = "NOT_IN_CORPUS"
CITATION_PATTERN = r"\[([^\]\s]+)\]"
# A trailing \b after "%" never matches (both sides are non-word characters), so
# percentages need their own alternative or every % claim silently verifies as empty.
VALUE_PATTERN = r"\b\d+(?:\.\d+)?\s?(?:kg|g|C)\b|\b\d+(?:\.\d+)?\s?%|\b\d+:\d+\b"
SYSTEM_PROMPT = (
    "Answer only from the provided context. If the context does not contain the answer, "
    f"reply exactly: {REFUSAL_TEXT}\n"
    "Cite the chunk you used after every claim, in square brackets, like [chunk_id]. "
    "Every sentence that states a fact must carry at least one citation."
)


def _embedding_function() -> embedding_functions.EmbeddingFunction:
    """Return the local sentence-embedding function used by every collection."""
    return embedding_functions.DefaultEmbeddingFunction()


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split leading --- front matter from the card body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_FENCE:
        return {}, text
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONT_MATTER_FENCE:
            end = index
            break
    if end is None:
        return {}, text
    front: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, _, value = line.partition(":")
            front[key.strip()] = value.strip()
    return front, "\n".join(lines[end + 1 :]).strip()


def _split_sections(body: str) -> dict[str, str]:
    """Split a card body into intro plus one entry per ## heading."""
    sections: dict[str, str] = {}
    current = "intro"
    buffer: list[str] = []
    for line in body.splitlines():
        if line.startswith(SECTION_HEADING_PREFIX):
            sections[current] = "\n".join(buffer).strip()
            current = line[len(SECTION_HEADING_PREFIX) :].strip().lower().replace(" ", "_")
            buffer = []
        else:
            buffer.append(line)
    sections[current] = "\n".join(buffer).strip()
    return {key: value for key, value in sections.items() if value}


def load_recipe_cards(cards_dir: Path = RECIPE_CARDS_DIR) -> list[dict[str, Any]]:
    """Load the new fermentation cards and split each into titled sections."""
    cards: list[dict[str, Any]] = []
    for path in sorted(cards_dir.glob(CARD_GLOB)):
        raw = path.read_text(encoding="utf-8")
        front, body = _parse_front_matter(raw)
        title_line = ""
        for line in body.splitlines():
            if line.startswith("# "):
                title_line = line[2:].strip()
                break
        cards.append(
            {
                "source_file": path.name,
                "recipe_id": front.get("recipe_id", ""),
                "title": front.get("title", title_line),
                "cuisine": front.get("cuisine", ""),
                "dietary_tags": front.get("dietary_tags", ""),
                "body": body,
                "sections": _split_sections(body),
            }
        )
    if not cards:
        raise FileNotFoundError(f"No cards matching {CARD_GLOB} in {cards_dir}")
    return cards


def parse_dietary_tags(dietary_tags: str) -> list[str]:
    """Split a comma-separated dietary_tags string into clean tags."""
    return [tag.strip() for tag in dietary_tags.split(",") if tag.strip()]


def _dietary_tag_flags(dietary_tags: str) -> dict[str, bool]:
    """Expand dietary tags into one boolean metadata flag each, for filtering."""
    return {
        f"{DIETARY_TAG_PREFIX}{tag.replace('-', '_')}": True
        for tag in parse_dietary_tags(dietary_tags)
    }


def _chunk_metadata(card: dict[str, Any], section: str, chunk_id: str) -> dict[str, Any]:
    """Build the metadata dict carried by every chunk."""
    metadata: dict[str, Any] = {
        "chunk_id": chunk_id,
        "source_file": card["source_file"],
        "recipe_id": card["recipe_id"],
        "cuisine": card["cuisine"],
        "dietary_tags": card["dietary_tags"],
        "section": section,
    }
    metadata.update(_dietary_tag_flags(card["dietary_tags"]))
    return metadata


def chunk_baseline(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Chunk a card into fixed-size overlapping character windows."""
    body = card["body"]
    chunks: list[dict[str, Any]] = []
    start = 0
    index = 0
    step = BASELINE_CHUNK_SIZE - BASELINE_CHUNK_OVERLAP
    while start < len(body):
        text = body[start : start + BASELINE_CHUNK_SIZE].strip()
        if text:
            chunk_id = f"{card['recipe_id']}::baseline::{index}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": text,
                    "metadata": _chunk_metadata(card, "window", chunk_id),
                }
            )
            index += 1
        start += step
    return chunks


def _split_table(section_text: str) -> tuple[list[str], list[str], list[str]]:
    """Split an ingredients section into table header lines, row lines and loose prose."""
    header: list[str] = []
    rows: list[str] = []
    prose: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("|"):
            if len(header) < 2:
                header.append(stripped)
            else:
                rows.append(stripped)
        else:
            prose.append(stripped)
    return header, rows, prose


def chunk_structure_aware(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Chunk a card so ingredient rows keep their table header and recipe title."""
    chunks: list[dict[str, Any]] = []
    sections = card["sections"]
    title = f"# {card['title']}"
    # The intro block still holds the H1 line; drop it so the title is not repeated.
    intro = "\n".join(
        line
        for line in sections.get("intro", "").splitlines()
        if not line.startswith("# ")
    ).strip()
    index = 0

    def add(text: str, section: str) -> None:
        nonlocal index
        chunk_id = f"{card['recipe_id']}::structure::{index}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "metadata": _chunk_metadata(card, section, chunk_id),
            }
        )
        index += 1

    # Ingredient rows travel with the title, the percentage basis and the table header.
    ingredients = sections.get(INGREDIENTS_SECTION, "")
    if ingredients:
        header, rows, prose = _split_table(ingredients)
        preamble = "\n".join(part for part in (title, intro, "## Ingredients", *header) if part)
        for start in range(0, len(rows), TABLE_ROWS_PER_CHUNK):
            batch = rows[start : start + TABLE_ROWS_PER_CHUNK]
            add("\n".join([preamble, *batch]), INGREDIENTS_SECTION)
        if prose:
            add("\n".join([title, "## Ingredients", *prose]), INGREDIENTS_SECTION)

    # Method prose is kept in its own chunks, grouped a few sentences at a time.
    method = sections.get(METHOD_SECTION, "")
    if method:
        sentences = [
            sentence.strip()
            for sentence in re.split(SENTENCE_SPLIT_PATTERN, method)
            if sentence.strip()
        ]
        for start in range(0, len(sentences), METHOD_SENTENCES_PER_CHUNK):
            batch = sentences[start : start + METHOD_SENTENCES_PER_CHUNK]
            add("\n".join([title, "## Method", " ".join(batch)]), METHOD_SECTION)

    # Any remaining section (the allergen note) becomes one titled chunk.
    for name, text in sections.items():
        if name in {"intro", INGREDIENTS_SECTION, METHOD_SECTION}:
            continue
        heading = name.replace("_", " ").title()
        add("\n".join([title, f"## {heading}", text]), name)

    return chunks


def build_index(collection_name: str, chunks: list[dict[str, Any]]) -> Collection:
    """Create a fresh collection and upsert chunks after validating metadata."""
    for chunk in chunks:
        source_file = chunk["metadata"].get("source_file", "")
        if not isinstance(source_file, str) or not source_file.strip():
            raise ValueError(
                f"chunk {chunk.get('chunk_id')!r} has empty source_file; refusing to upsert"
            )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    existing = [existing_collection.name for existing_collection in client.list_collections()]
    if collection_name in existing:
        client.delete_collection(collection_name)
    collection = client.create_collection(
        name=collection_name,
        embedding_function=_embedding_function(),
        # Record the model on the index so a collection states what embedded it.
        metadata={"hnsw:space": "cosine", "embedding_model": EMBEDDING_MODEL},
    )
    collection.upsert(
        ids=[chunk["chunk_id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )
    return collection


def search(collection: Collection, query: str, top_k: int = TOP_K) -> list[dict[str, Any]]:
    """Return the top_k chunks for a query, best first."""
    raw = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    results: list[dict[str, Any]] = []
    for position in range(len(raw["ids"][0])):
        metadata = raw["metadatas"][0][position]
        results.append(
            {
                "rank": position + 1,
                "chunk_id": raw["ids"][0][position],
                "text": raw["documents"][0][position],
                "score": round(1.0 - raw["distances"][0][position], 4),
                "recipe_id": metadata.get("recipe_id", ""),
                "section": metadata.get("section", ""),
                "source_file": metadata.get("source_file", ""),
                "cuisine": metadata.get("cuisine", ""),
                "dietary_tags": metadata.get("dietary_tags", ""),
            }
        )
    return results


def search_with_dietary_filter(
    collection: Collection, query: str, dietary_tag: str, top_k: int = TOP_K
) -> list[dict[str, Any]]:
    """Return the top_k chunks for a query, restricted to one dietary tag."""
    flag = f"{DIETARY_TAG_PREFIX}{dietary_tag.strip().replace('-', '_')}"
    raw = collection.query(
        query_texts=[query],
        n_results=top_k,
        where={flag: True},
        include=["documents", "metadatas", "distances"],
    )
    results: list[dict[str, Any]] = []
    for position in range(len(raw["ids"][0])):
        metadata = raw["metadatas"][0][position]
        results.append(
            {
                "rank": position + 1,
                "chunk_id": raw["ids"][0][position],
                "text": raw["documents"][0][position],
                "score": round(1.0 - raw["distances"][0][position], 4),
                "recipe_id": metadata.get("recipe_id", ""),
                "section": metadata.get("section", ""),
                "source_file": metadata.get("source_file", ""),
                "cuisine": metadata.get("cuisine", ""),
                "dietary_tags": metadata.get("dietary_tags", ""),
            }
        )
    return results


def _tokenize(text: str) -> list[str]:
    """Lower-case and split text into lexical tokens, keeping quantities intact."""
    return re.findall(TOKEN_PATTERN, text.lower())


_CORPUS_CACHE: dict[str, dict[str, Any]] = {}


def _load_corpus(collection: Collection) -> dict[str, Any]:
    """Read every chunk once and cache the tokenised corpus for lexical scoring."""
    if collection.name in _CORPUS_CACHE:
        return _CORPUS_CACHE[collection.name]
    stored = collection.get(include=["documents", "metadatas"])
    tokenised = [_tokenize(doc) for doc in stored["documents"]]
    document_frequency: dict[str, int] = {}
    for tokens in tokenised:
        for token in set(tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1
    corpus = {
        "ids": stored["ids"],
        "documents": stored["documents"],
        "metadatas": stored["metadatas"],
        "tokenised": tokenised,
        "document_frequency": document_frequency,
        "average_length": sum(len(tokens) for tokens in tokenised) / max(len(tokenised), 1),
    }
    _CORPUS_CACHE[collection.name] = corpus
    return corpus


def _as_result(corpus: dict[str, Any], index: int, rank: int, score: float) -> dict[str, Any]:
    """Shape one corpus entry like a search() result."""
    metadata = corpus["metadatas"][index]
    return {
        "rank": rank,
        "chunk_id": corpus["ids"][index],
        "text": corpus["documents"][index],
        "score": round(score, 4),
        "recipe_id": metadata.get("recipe_id", ""),
        "section": metadata.get("section", ""),
        "source_file": metadata.get("source_file", ""),
        "cuisine": metadata.get("cuisine", ""),
        "dietary_tags": metadata.get("dietary_tags", ""),
    }


def search_bm25(
    collection: Collection, query: str, top_k: int = TOP_K
) -> list[dict[str, Any]]:
    """Return the top_k chunks by BM25 lexical relevance, best first."""
    corpus = _load_corpus(collection)
    total_documents = len(corpus["ids"])
    query_tokens = _tokenize(query)
    scored: list[tuple[float, int]] = []
    for index, tokens in enumerate(corpus["tokenised"]):
        length = len(tokens)
        score = 0.0
        for token in query_tokens:
            frequency = tokens.count(token)
            if not frequency:
                continue
            document_frequency = corpus["document_frequency"].get(token, 0)
            idf = math.log(
                1 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = frequency + BM25_K1 * (
                1 - BM25_B + BM25_B * length / max(corpus["average_length"], EPSILON)
            )
            score += idf * frequency * (BM25_K1 + 1) / denominator
        if score > 0:
            scored.append((score, index))
    scored.sort(key=lambda pair: (-pair[0], corpus["ids"][pair[1]]))
    return [
        _as_result(corpus, index, rank, score)
        for rank, (score, index) in enumerate(scored[:top_k], start=1)
    ]


def search_hybrid_rrf(
    collection: Collection, query: str, top_k: int = TOP_K
) -> list[dict[str, Any]]:
    """Fuse dense and BM25 rankings with reciprocal rank fusion, best first."""
    dense = search(collection, query, HYBRID_CANDIDATE_DEPTH)
    lexical = search_bm25(collection, query, HYBRID_CANDIDATE_DEPTH)
    # RRF fuses RANKS, never raw scores: cosine and BM25 are not on a shared scale.
    fused: dict[str, float] = {}
    for ranking in (dense, lexical):
        for hit in ranking:
            fused[hit["chunk_id"]] = fused.get(hit["chunk_id"], 0.0) + 1.0 / (
                RRF_K + hit["rank"]
            )
    corpus = _load_corpus(collection)
    position_of = {chunk_id: index for index, chunk_id in enumerate(corpus["ids"])}
    ordered = sorted(fused.items(), key=lambda pair: (-pair[1], pair[0]))
    return [
        _as_result(corpus, position_of[chunk_id], rank, score)
        for rank, (chunk_id, score) in enumerate(ordered[:top_k], start=1)
    ]


def build_generation_prompt(question: str, contexts: list[dict[str, Any]]) -> str:
    """Render retrieved chunks and the question into the user prompt."""
    blocks = [f"[{chunk['chunk_id']}]\n{chunk['text']}" for chunk in contexts]
    return "CONTEXT:\n\n" + "\n\n---\n\n".join(blocks) + f"\n\nQUESTION: {question}"


def _values_in(text: str) -> set[str]:
    """Extract normalised numeric values such as 20g or 75% from text."""
    return {match.group(0).replace(" ", "") for match in re.finditer(VALUE_PATTERN, text)}


def verify_citations(collection: Collection, answer: str) -> list[dict[str, Any]]:
    """Check each cited chunk exists and contains the values claimed beside it."""
    checks: list[dict[str, Any]] = []
    sentences = [
        sentence.strip()
        for sentence in re.split(SENTENCE_SPLIT_PATTERN, answer)
        if sentence.strip()
    ]
    for sentence in sentences:
        for chunk_id in re.findall(CITATION_PATTERN, sentence):
            stored = collection.get(ids=[chunk_id], include=["documents"])
            exists = bool(stored["ids"])
            chunk_text = stored["documents"][0] if exists else ""
            claimed = _values_in(re.sub(CITATION_PATTERN, "", sentence))
            missing = sorted(claimed - _values_in(chunk_text))
            checks.append(
                {
                    "chunk_id": chunk_id,
                    "exists": exists,
                    "claimed_values": sorted(claimed),
                    "missing_values": missing,
                    "ok": exists and not missing,
                }
            )
    return checks


def _retry_delay(message: str) -> float:
    """Read the server's suggested retry delay out of a rate-limit message."""
    match = re.search(RETRY_DELAY_PATTERN, message)
    return float(match.group(1)) + 1.0 if match else GEMINI_DEFAULT_RETRY_SECONDS


def is_rate_limit_error(error: BaseException) -> bool:
    """Report whether an exception is the API refusing on quota rather than a real fault."""
    message = str(error)
    return "429" in message or "quota" in message.lower()


def _gemini_generate(system_prompt: str, user_prompt: str) -> str:
    """Send the grounded prompt to the Gemini API, retrying on rate limits."""
    from google import genai

    client = genai.Client()
    for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):
        try:
            interaction = client.interactions.create(
                model=GEMINI_MODEL,
                system_instruction=system_prompt,
                input=user_prompt,
                generation_config={"thinking_level": GEMINI_THINKING_LEVEL},
            )
        except Exception as error:  # only rate limits are retried; anything else re-raises
            if not is_rate_limit_error(error) or attempt == GEMINI_MAX_ATTEMPTS:
                raise
            delay = _retry_delay(str(error))
            print(f"  rate limited, retrying in {delay:.0f}s (attempt {attempt})")
            time.sleep(delay)
        else:
            return interaction.output_text or ""
    raise RuntimeError("exhausted Gemini retry attempts")


def answer_with_citations(
    collection: Collection,
    question: str,
    generate: Any = _gemini_generate,
    top_k: int = TOP_K,
    retriever: Any = search_hybrid_rrf,
) -> dict[str, Any]:
    """Answer a question from retrieved context and verify every citation."""
    contexts = retriever(collection, question, top_k)
    user_prompt = build_generation_prompt(question, contexts)
    answer = generate(SYSTEM_PROMPT, user_prompt)
    refused = answer.strip() == REFUSAL_TEXT
    checks = [] if refused else verify_citations(collection, answer)
    return {
        "question": question,
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "contexts": contexts,
        "answer": answer,
        "refused": refused,
        "citation_checks": checks,
        "all_citations_ok": all(check["ok"] for check in checks) if checks else refused,
    }


def run_retrieval_eval(
    questions: list[dict[str, Any]], collection: Collection, top_k: int = TOP_K
) -> list[dict[str, Any]]:
    """Search every question and record whether the expected recipe is in top_k."""
    rows: list[dict[str, Any]] = []
    for question in questions:
        hits = search(collection, question["question"], top_k)
        expected_recipe = question["expected_recipe_id"]
        expected_section = question["expected_section"]
        found = any(hit["recipe_id"] == expected_recipe for hit in hits)
        section_found = any(
            hit["recipe_id"] == expected_recipe and hit["section"] == expected_section
            for hit in hits
        )
        rows.append(
            {
                "id": question["id"],
                "question": question["question"],
                "expected_recipe_id": expected_recipe,
                "expected_section": expected_section,
                "needs_table_row": question["needs_table_row"],
                "hit": found,
                "section_hit": section_found,
                "top1_recipe_id": hits[0]["recipe_id"] if hits else "",
                "results": hits,
            }
        )
    return rows
