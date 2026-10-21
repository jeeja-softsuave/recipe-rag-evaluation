# Fresh-eyes review: Thursday

**For the reviewer from another squad.** Please follow these steps cold, using only
`README.md`. Do not ask the author for help until you are stuck. Getting stuck is the
finding: write down where and why.

**Reviewer:** __________________  **Squad:** __________________  **Date:** __________

## Part A: clone and run, using only the README (no API key needed until step A4)

| Step | Do this | Worked? | Where you stumbled (exact words of the error, or what confused you) |
|---|---|---|---|
| A1 | Clone, create the venv, `pip install -r requirements.txt` | | |
| A2 | `pantry.py index` | | |
| A3 | `test_pantry.py`: expect 13/13 checks, 0 API calls | | |
| A4 | Add your own key to `.env`, then `pantry.py ask "<a question of your own>"` | | |
| A5 | `pantry.py trace <the trace id A4 printed>` | | |

## Part B: call my MCP server from YOUR client (requirement 3)

Use your own MCP client: MCP Inspector, Claude Desktop, Claude Code, or your own Week 9
host. Connect it to `pantry.py serve` (config in the README).

| Step | Do this | Result |
|---|---|---|
| B1 | List the tools. How many did your client discover, and what are their names? | |
| B2 | `check_allergens` for `kallappam-batter-02`, avoid `["nuts"]`. What verdict, and which version? | |
| B3 | The same call with `version: "original"`. What verdict now? (This is the trap the system must avoid.) | |
| B4 | `scale_recipe` for `idli-batter-05` to `120`. Did the ferment time change? | |
| B5 | `safe_temperature` for something not on the chart (try "pork belly"). Did it guess? | |
| B6 | Try to break it: a wrong argument, an allergen spelled your way ("peanuts"), an empty query | |

## Part C: your verdict, in your words

1. **The one place you would not trust this with a nut-allergic child:**
2. **The thing that was hardest to understand from the README:**
3. **Anything that worked better than you expected:**

---

## Author's response (filled in after the review, dated)

| Stumble | What I changed | Commit / file |
|---|---|---|
| | | |
