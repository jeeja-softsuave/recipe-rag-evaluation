"""Build a question population from the cards themselves, then draw a seeded sample."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from recipe_rag import INGREDIENTS_SECTION, load_recipe_cards

SEED = 20260824
RANDOM_SAMPLE_SIZE = 20
DEMO_SAMPLE_SIZE = 10
POPULATION_FILE = Path(__file__).parent / "question_population.jsonl"
RANDOM_SAMPLE_FILE = Path(__file__).parent / "sample_random.json"
DEMO_SAMPLE_FILE = Path(__file__).parent / "sample_demo.json"
EVAL_QUESTIONS_FILE = Path(__file__).parent / "eval_questions.json"
GOLDEN_SET_FILE = Path(__file__).parent / "golden_set.jsonl"
ANSWER_CACHE_FILE = Path(__file__).parent / "answer_cache.json"

# Templates are applied to every recipe and every ingredient the cards contain, so the
# population is enumerated from the data rather than chosen by hand.
INGREDIENT_TEMPLATES = (
    "how much {ingredient} for {dish}",
    "{dish} {ingredient} quantity",
    "how many grams of {ingredient} in {dish}",
)
RECIPE_TEMPLATES = (
    "how do i make {dish}",
    "how long does {dish} take to ferment",
    "what temperature for {dish}",
    "whats the yield of {dish}",
    "is {dish} safe for a dairy allergy",
    "what ratio does {dish} use",
    "how long do i steam {dish}",
    "can i leave {dish} overnight",
)
OUT_OF_CORPUS_TEMPLATES = (
    "how many calories in {dish}",
    "what is the protein content of {dish}",
    "where can i buy ingredients for {dish}",
)
UNRELATED_QUESTIONS = (
    "what is the capital of France",
    "how do i reset my wifi router",
    "who won the cricket match yesterday",
)


def short_dish_name(title: str) -> str:
    """Turn a card title into the name a user would actually type."""
    return title.split("(")[0].strip().lower()


def ingredient_names(card: dict[str, Any]) -> list[str]:
    """Read ingredient names out of a card's table, ignoring header and separator rows."""
    section = card["sections"].get(INGREDIENTS_SECTION, "")
    names: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= set("|- "):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0].lower() == "ingredient":
            continue
        names.append(cells[0].split(",")[0].strip().lower())
    return names


def build_population(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enumerate every template against every recipe and ingredient in the corpus."""
    population: list[dict[str, Any]] = []

    def add(question: str, kind: str, recipe_id: str) -> None:
        population.append(
            {
                "candidate_id": f"c{len(population) + 1:03d}",
                "question": question,
                "kind": kind,
                "about_recipe_id": recipe_id,
            }
        )

    for card in cards:
        dish = short_dish_name(card["title"])
        for ingredient in ingredient_names(card):
            for template in INGREDIENT_TEMPLATES:
                add(
                    template.format(ingredient=ingredient, dish=dish),
                    "ingredient",
                    card["recipe_id"],
                )
        for template in RECIPE_TEMPLATES:
            add(template.format(dish=dish), "recipe", card["recipe_id"])
        for template in OUT_OF_CORPUS_TEMPLATES:
            add(template.format(dish=dish), "out_of_corpus", card["recipe_id"])
    for question in UNRELATED_QUESTIONS:
        add(question, "unrelated", "")
    return population


def load_demo_questions() -> list[dict[str, Any]]:
    """Collect the questions actually used in demos and reviews, for the bonus sample."""
    demo: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(question: str, origin: str) -> None:
        if question in seen:
            return
        seen.add(question)
        demo.append({"question": question, "origin": origin})

    for item in json.loads(EVAL_QUESTIONS_FILE.read_text(encoding="utf-8")):
        add(item["question"], "eval_questions.json")
    for line in GOLDEN_SET_FILE.read_text(encoding="utf-8").strip().splitlines():
        add(json.loads(line)["question"], "golden_set.jsonl")
    for question in json.loads(ANSWER_CACHE_FILE.read_text(encoding="utf-8")):
        add(question, "live demo")
    return demo


def main() -> None:
    """Write the population and both seeded samples, printing the seed used."""
    cards = load_recipe_cards()
    population = build_population(cards)
    POPULATION_FILE.write_text(
        "\n".join(json.dumps(item) for item in population) + "\n", encoding="utf-8"
    )

    random_sample = random.Random(SEED).sample(population, RANDOM_SAMPLE_SIZE)
    RANDOM_SAMPLE_FILE.write_text(
        json.dumps({"seed": SEED, "population_size": len(population),
                    "sample": random_sample}, indent=2),
        encoding="utf-8",
    )

    demo = load_demo_questions()
    demo_sample = random.Random(SEED).sample(demo, DEMO_SAMPLE_SIZE)
    DEMO_SAMPLE_FILE.write_text(
        json.dumps({"seed": SEED, "demo_set_size": len(demo), "sample": demo_sample}, indent=2),
        encoding="utf-8",
    )

    print(f"seed: {SEED}")
    print(f"population: {len(population)} candidate questions -> {POPULATION_FILE.name}")
    print(f"random sample: {RANDOM_SAMPLE_SIZE} -> {RANDOM_SAMPLE_FILE.name}")
    print(f"demo set: {len(demo)} questions, sampled {DEMO_SAMPLE_SIZE} -> {DEMO_SAMPLE_FILE.name}")
    print("\nthe 20 sampled questions:")
    for item in random_sample:
        print(f"  {item['candidate_id']}  [{item['kind']:<13}] {item['question']}")


if __name__ == "__main__":
    main()
