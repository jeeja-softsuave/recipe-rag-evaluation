# Week 9, requirement 5: docstring as prompt, recoverable error

**Tool rewritten:** `substitute_ingredient` on my own server, [recipe_server.py](recipe_server.py).
`tools.py` is untouched, so the Week 7/8 results still reproduce. The rewrite lives in the
MCP wrapper only.

**Failing call:** `substitute_ingredient({"ingredient": "curd", "avoid": "dairy"})`.
The substitution table does hold a dairy swap, under the card's exact name
`Thick sour curd`. So this is a naming miss, not a dead end.

## What changed

### Docstring

The MCP SDK publishes the docstring as the tool `description`, so the docstring is the prompt.

**Before**, as a plain port of the Python docstring, taken verbatim from `tools_before.json`:

> Replace one ingredient to satisfy one dietary constraint.

The parameter descriptions were "The ingredient to replace." and "The dietary constraint."

**After**, taken verbatim from `tools/list` on the rewritten server:

> Replace exactly ONE ingredient to satisfy exactly ONE dietary constraint, from the app's
> recorded substitution table, and report which allergens the replacement itself contains.
>
> Use it when the user must avoid dairy, coconut, nuts, gluten, alcohol, yeast or soy and a
> recipe ingredient contains it. Name the ingredient exactly as the card names it; a short or
> everyday name will not match.
>
> Reading the result:
> - substituted true: read substitute_contains. If the replacement contains something else
>   the user avoids, call this tool again on the replacement.
> - substituted false, recoverable true: the name did not match. Retry with a name from
>   did_you_mean.
> - substituted false, recoverable false: no substitute is recorded. Tell the user that, and
>   do not suggest substitutes of your own: an unrecorded swap has unchecked allergens.
>
> Does not find recipes and does not scale quantities.

The new `ingredient` parameter description reads: "The ingredient exactly as the recipe
card or an earlier substitute result names it, e.g. 'Thick sour curd', not 'curd'."

### Error path

The old server returned the same message for two different cases:
- a spelling miss, which the model could fix;
- a genuine dead end, where nothing is recorded.

The new server tells them apart.

| Case | Before | After |
|---|---|---|
| Unknown name (`curd`, dairy) | `"reason": "no substitution recorded for that ingredient and constraint"` | `"reason": "no ingredient named 'curd' in the substitution table: try 'Thick sour curd'", "recoverable": true, "did_you_mean": ["Thick sour curd"]` |
| Known name, nothing recorded (`Thick sour curd`, nuts) | the same sentence as above | `"reason": "'Thick sour curd' is in the substitution table, but no substitute is recorded for avoid=nuts (recorded only for: dairy). No safe substitute exists in the data; do not invent one.", "recoverable": false` |
| Unknown constraint (`eggs`) | rejected by the schema enum, `isError: true` | unchanged, still rejected before the function runs |

## Transcript: the same failing call, handled both ways

These come from a controlled replay: [replay_failing_call.py](replay_failing_call.py), with
the output stored in [error_replay.json](error_replay.json). It works like this:
1. One real model call is made with the **baseline** tool descriptions, copied from
   `tools_before.json`. The model emitted the failing call itself.
2. That single interaction (`lap1_interaction_id` in the JSON) is then continued twice.
   Branch A gets the old answer and the old descriptions. Branch B gets the new server's
   answer and the new descriptions.

Everything else is identical: the request, the model, the system instruction, and the lap-1
call. The replay uses `mcp_agent.py` without modifying it.

Request: *"What can I use instead of curd if I'm avoiding dairy?"* (server one only)

### Before: old docstring, old error

```
lap 1  model -> substitute_ingredient({"ingredient": "curd", "avoid": "dairy"})
       tool  -> {"substituted": false, "ingredient": "curd", "avoid": "dairy",
                 "reason": "no substitution recorded for that ingredient and constraint"}
lap 2  model -> substitute_ingredient({"avoid": "dairy", "ingredient": "yogurt"})      <- blind guess
       tool  -> {"substituted": false, "ingredient": "yogurt", "avoid": "dairy",
                 "reason": "no substitution recorded for that ingredient and constraint"}
lap 3  model -> answer:
       "I don't have a specific pre-recorded substitution in the database for curd when
        avoiding dairy, but common dairy-free alternatives to curd (yogurt) include:
        * Coconut Curd / Coconut Milk Yogurt ...
        * Soy Curd / Soy Yogurt ...
        * Cashew or Almond Curd ...
        * Peanut Curd: A traditional homemade plant-based curd alternative ..."
```

### After: new docstring, recoverable error

```
lap 1  model -> substitute_ingredient({"ingredient": "curd", "avoid": "dairy"})       <- same call
       tool  -> {"substituted": false, "ingredient": "curd", "avoid": "dairy",
                 "reason": "no ingredient named 'curd' in the substitution table: try 'Thick sour curd'",
                 "recoverable": true, "did_you_mean": ["Thick sour curd"]}
lap 2  model -> substitute_ingredient({"avoid": "dairy", "ingredient": "Thick sour curd"})
       tool  -> {"substituted": true, "ingredient": "Thick sour curd", "avoid": "dairy",
                 "substitute": "coconut milk yoghurt", "substitute_contains": ["coconut"],
                 "source": "curated"}
lap 3  model -> answer:
       "Instead of thick sour curd, you can use coconut milk yoghurt to avoid dairy.
        Please note that coconut milk yoghurt contains coconut."
```

## What the replay shows

1. **The old error made the model guess, then invent.** It could not tell "wrong name" from
   "nothing exists". It retried with a spelling of its own (`yogurt`), got the same sentence
   back, and fell back on its own knowledge. Three of its four suggestions contain nuts or
   peanut: cashew, almond and peanut curd. Neither the tool nor the data checked their
   allergens.
   - This happened even though the system instruction says *"Never state an allergen,
     substitution or nutrition value that no tool returned."* The system prompt did not hold.
     The tool result is what changed the behaviour.
2. **The new error made recovery a single step.** The model took `did_you_mean[0]`, retried
   once, and passed the coconut warning from `substitute_contains` through to the user.
3. **Before vs after:**

   | | Before | After |
   |---|---|---|
   | Grounded answer | no | yes |
   | Unchecked substitutes stated | 4 | 0 |
   | Suggestions containing nuts or peanut | 3 | 0 |
   | Laps | 3 | 3 |

## Two natural runs, not replayed (in `mcp_traces.jsonl`)

- **Old server, natural run:** label `P4-before old docstring+error, server one only`. The
  model made the same failing `curd` call. It then answered with a made-up list that also
  includes almond and cashew yoghurt. The failure is not a replay artefact.
- **New server, natural run:** label `P4-after new docstring+recoverable error, server one only`.
  The model **never made the failing call**. The new docstring ("name the ingredient exactly
  as the card names it") led it to call `search_recipes` first and copy `Thick sour curd`.
  The docstring prevented the failure before the error message was ever needed. This is why
  the replay above was needed to show the same failing call being handled.

## Caveats

- This is n = 1 for each branch. The replay makes that one comparison fair; it does not make
  it a rate.
- The "before" docstring is a naive port: the one-line Python docstring from `tools.py`. The
  Week 7 hand-written `TOOL_SPECS` description was richer. What the brief tests is exactly
  what a plain SDK port publishes.
- **With both servers connected, the failure did not occur at all** (label `P4-before old
  docstring+error`). Server two's attached allergen matrix lists `Thick sour curd: dairy`,
  and the model took the exact name from that context. This is why the before/after runs use
  server one only.
