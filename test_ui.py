"""Check the web app's tool screens and read-only data with zero API calls.

Every screen except Ask calls the MCP server's tool functions directly, with no model, so
these checks run against a real server in this process and expect exact answers.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any

import ui

CHECKS: list[tuple[str, bool]] = []


def check(label: str, passed: bool) -> None:
    CHECKS.append((label, passed))
    print(f"  {'PASS' if passed else 'FAIL'}  {label}")


def main() -> None:
    """Run every check; exit non-zero if any failed."""
    server = ui.make_server(0)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def call(path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    status, meta = call("/api/meta")
    check("meta lists the recipes, allergens, chart and substitution table",
          status == 200 and "kallappam-batter-02" in meta["recipe_ids"] and "nuts" in meta["allergens"]
          and meta["chart"] and meta["substitutions"])

    status, cards = call("/api/recipes")
    keys = {c["key"] for c in cards}
    check("recipes include both kallappam versions, current and superseded",
          {"kallappam-batter-02@original", "kallappam-batter-02@reformulated-2025"} <= keys
          and {c["status"] for c in cards} == {"current", "superseded"})

    status, result = call("/api/check", {"recipe_id": "kallappam-batter-02", "avoid": ["nuts"]})
    check("check: current kallappam is unsafe for nuts (the reformulation added cashew)",
          status == 200 and result["verdict"] == "unsafe"
          and result["citation"] == "kallappam-batter-02@reformulated-2025")
    status, result = call("/api/check", {"recipe_id": "kallappam-batter-02", "avoid": ["nuts"],
                                         "version": "original"})
    check("check: the superseded original was nut-free, and says it is superseded",
          result["verdict"] == "no_declared_allergen" and result["status"] == "superseded")
    status, result = call("/api/check", {"recipe_id": "idli-batter-05", "avoid": ["nuts"]})
    check("check: idli is may-contain for nuts", result["verdict"] == "may_contain")
    check("check: an unknown recipe is refused",
          call("/api/check", {"recipe_id": "../.env", "avoid": ["nuts"]})[0] == 400)
    check("check: an allergen outside the declared set is refused",
          call("/api/check", {"recipe_id": "idli-batter-05", "avoid": ["peanut"]})[0] == 400)
    check("check: an empty avoid list is refused",
          call("/api/check", {"recipe_id": "idli-batter-05", "avoid": []})[0] == 400)

    status, result = call("/api/scale", {"recipe_id": "idli-batter-05", "target_yield": 120})
    urad = next(i for i in result["ingredients"] if "urad" in i["ingredient"].lower())
    check("scale: idli x4 gives 800 g urad dal and the ferment time unchanged",
          status == 200 and urad["grams"] == 800.0 and result["times_unchanged"]["ferment_hours"] == "10-12")
    check("scale: a yield over the maximum is refused",
          call("/api/scale", {"recipe_id": "idli-batter-05", "target_yield": 10_000})[0] == 400)
    check("scale: a non-number yield is refused",
          call("/api/scale", {"recipe_id": "idli-batter-05", "target_yield": "lots"})[0] == 400)

    status, result = call("/api/temperature", {"item": "chicken"})
    check("temperature: chicken is 74 C", result["found"] and result["min_internal_c"] == 74)
    status, result = call("/api/temperature", {"item": "pork belly"})
    check("temperature: a food not in the chart is refused, not guessed", status == 200 and not result["found"])
    check("temperature: an over-long item is refused", call("/api/temperature", {"item": "x" * 500})[0] == 400)

    status, result = call("/api/substitute", {"ingredient": "Grated coconut", "avoid": "coconut"})
    check("swap: grated coconut becomes cashew paste, and says it contains nuts",
          result["substituted"] and result["substitute_contains"] == ["nuts"])
    status, result = call("/api/substitute", {"ingredient": "coconut milk", "avoid": "coconut"})
    check("swap: a near miss is a recoverable error with a suggestion",
          not result["substituted"] and result["did_you_mean"])

    status, rows = call("/api/history")
    check("history returns redacted questions only, never the raw question or its hash",
          status == 200 and all("question" not in r and "question_hash" not in r for r in rows))
    check("an unknown trace id is a 404", call("/api/trace/t-nope")[0] == 404)

    req = urllib.request.Request(base + "/api/check", data=b"{}", headers={
        "Content-Type": "application/json", "Origin": "http://evil.example"})
    try:
        urllib.request.urlopen(req)
        refused = False
    except urllib.error.HTTPError as error:
        refused = error.code == 403
    check("the tool screens refuse a cross-site POST too", refused)

    server.shutdown()
    failed = [label for label, passed in CHECKS if not passed]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} UI checks passed, 0 API calls")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
