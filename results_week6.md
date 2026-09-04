# Week 6 - validating the LLM judge

## Headline

A judge scoring 91% agreement caught 0 of 3 labelled failures. The 91% was an
artefact of the label distribution: 31 of 34 cases were PASS, so an unconditional
PASS scores 91% too. Iterating the prompt raised agreement to 94%, but two of the
three "failures" it originally missed turned out to be my own bad labels, so the
real improvement is one genuine catch bought at the price of one new false failure.

## Numbers

| | judge v1 | judge v2 |
|---|---|---|
| agreement | 91% (31/34) | 94% (32/34) |
| too lenient (human FAIL, judge PASS) | 3 | 1 |
| too strict (human PASS, judge FAIL) | 0 | 1 |
| labelled defects caught | 0 of 3 | 2 of 3 |

Judge: gemini-3.6-flash, 34 cases, one binary SUPPORTED criterion.
Five deterministic checks live in assertions.py and are not judged by the model.

## The assertion/judge split

judge_v0.txt was drafted with 6 criteria and never run. Five were decidable by
string and number handling, so they were deleted from the prompt and reimplemented:

  refusal_is_exact, cited_chunks_exist, one_id_per_bracket,
  quantities_parse, allergen_warning_present

That left 1 judged criterion. The split paid off immediately: the assertions catch
3 failures the judge is never asked about (s01 and r01 pack two chunk ids into one
bracket; r02 answers about a dairy recipe without naming the dairy risk), at zero
API cost and with no drift between runs.

## Prediction versus outcome

prediction.txt was committed in 506ed07, before judge_v2.txt was run.

  Predicted: 97% (33/34). Actual: 94% (32/34). Off by one case.
  Predicted v2 would catch r08 and s18 (both shown as examples). It did.
  Predicted v2 would catch r09 at ~70% confidence. It did NOT.
  Named risk was over-correction on the ~20 correct refusals. It happened: s22.

Both predicted mechanisms fired; the point estimate was still too optimistic.

## The two disagreements - who was right

### s22: the human was right, the judge was wrong

Question: can i replace the 4 hour soak in kallappam with an overnight soak.
The app refused. I labelled PASS. Judge v2 said FAIL, reasoning that
[kallappam-batter-02::structure::4] says leaving it overnight goes sour and flat,
so refusing was ungrounded.

The judge conflated two different steps. That chunk is about the FERMENT - "it needs
only 4 to 5 hours at 28C ... it will go sour and flat if left overnight". The
question was about the 4-hour SOAK, in chunk ::3. The card says nothing about
substituting an overnight soak. The app was right to refuse and I was right to pass
it. This is precisely the over-correction the prediction named: the new
"check the context before accepting a refusal" instruction made v2 grab a
superficially matching phrase.

### r09: the judge was right, the human was wrong

Question: what ratio does kallappam batter use. The app refused. I labelled FAIL,
on the grounds that the retrieved chunk states "Hydration: 84%". Judge v2 said PASS,
reasoning that the context specifies no named ratio for kallappam.

The corpus settles this against me. "Rice to dal ratio" is a distinct labelled field:
idli states "Rice to dal ratio: 4:1", kuzhi paniyaram states "3:1". Kallappam and
sanna have no dal and state only Hydration. In the corpus's own vocabulary kallappam
has no ratio, so the refusal was defensible and my FAIL label was at best contestable.

This has a consequence I have to follow through. r08 (sanna) is the identical
situation, and v2 only marked it FAIL because I had put it in the prompt as a worked
example of a wrong refusal. I taught the judge my own mistake, and it obediently
reproduced it. That is why it "caught" r08 but not r09 - not generalisation, and not
even a correct rule.

## What that means for the headline

Re-reading the set with r08 and r09 treated as ambiguous rather than as failures:

  - s18 is the only unambiguous defect: it cites a chunk for "1.5g" when that chunk
    says 3g and gives no scaling rule.
  - v1 missed s18. v2 catches it. That is a real improvement of one case.
  - v2 also introduced a real regression, s22, a correct refusal marked FAIL.
  - Net genuine change: roughly zero. The visible 91% to 94% rise is largely the
    judge agreeing with two labels that were themselves wrong.

## Limitations, stated rather than discovered later

1. Degenerate label distribution. 31 of 34 labels are PASS, because the corpus
   contains exactly one stated substitution (sanna toddy to a 3g dry yeast slurry),
   so nearly every substitution question correctly refuses. Agreement is therefore a
   weak signal and the direction split matters more than the percentage.
2. Label quality is the binding constraint, not judge quality. Two of my three FAIL
   labels were contestable, and that error propagated straight into v2 through the
   few-shot examples. A judge cannot be validated past the quality of its labels.
3. Verdicts were proposed by Claude and reviewed by hand, recorded in the
   labelled_by field of labels_25.json rather than presented as independent human
   labels.
4. s21, s22, s24 and s25 exercise process swaps rather than ingredient swaps, which
   the single criterion covers only awkwardly - visible in s22 being the one case
   where the criterion's refusal clause and the question came apart.

## What I would do next

Fix the labels before touching the judge again. Specifically: drop r08 and r09 or
relabel them PASS, then rebuild v2's few-shot examples from s18 and s22 - one
derived-number failure and one over-strict refusal - so the prompt teaches both
error directions instead of only leniency.

## Ordering evidence

  bba29d5  34 labels committed, before any judge run
  506ed07  prediction.txt and judge_v2.txt, before v2 was run

No judge verdicts exist anywhere earlier in history.

## Reproduce

  python run_eval.py                 # assertions plus judge verdicts, pass rate by mode
  python run_judge.py v1|v2          # refuses unless labels are committed and clean
  python measure_agreement.py v1|v2  # agreement, split by error direction
