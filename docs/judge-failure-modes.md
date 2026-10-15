# LLM judge failure modes

Implementation: [`judge.py`](../src/aep/evaluators/judge.py). Machinery tests:
[`test_bias_mitigation.py`](../tests/test_bias_mitigation.py). Source review:
2026-10-10. Model numbers remain historical 2026-08-04 evidence.

## Position bias

The judge compares the SUT answer and reference in both orders. When the mapped
verdicts disagree, the pairwise result is recorded as a tie and the flip is
counted. A scripted always-prefers-first judge is caught by the tests.

This verifies the detector's mechanics, not the real judge's reliability. The
historical flip rate **0.2667 exceeds the target <0.10**. Inconsistency may involve
position sensitivity, sampling variability or ambiguous comparisons; this small
run does not isolate the cause. Invalid pairwise outputs omit a flip score, so
inspect coverage as well. Pairwise ties do not change the separate rubric score.

## Verbosity bias

The rubric asks for coverage of enumerated required points and explicitly says
not to reward length. The scorecard reports Pearson correlation between answer
length and `judge_overall`. The historical 0.2686 is inside the |r|<0.30 target,
but that is an observational monitor, not proof of causation or absence of bias.
Synthetic tests verify the correlation calculation.

## Self-preference

The constructor rejects equal SUT and judge **deployment names** unless
`AEP_ALLOW_SAME_JUDGE=1`. Different aliases do not establish different models.
The historical workflow sets the override. The original notes attribute that
choice to model quota, which has not been rechecked in this refresh.

This limitation is described here, but the current run artifact does not record
the override explicitly, and generated scorecards do not automatically attach a
same-model warning. Record model identity and configuration when interpreting a
run. Even regression deltas can be affected by model changes, noise or bias.

## Human agreement and malformed output

`aep calibrate` computes Spearman correlation and linear-weighted Cohen's kappa
against human labels. The repository has a 20-case annotation template, not a
completed human calibration. No agreement result can be claimed yet.

Rubric outputs are checked for expected keys and score ranges. Current retry
logic can issue a third request whose response is discarded without validation.
After failed validation, `judge_error=1` is emitted separately from quality
scores. Pairwise malformed output is handled differently and can omit a score;
API exceptions are not uniformly converted into per-metric missing values.
These are existing implementation gaps, recorded in [limitations](limitations.md).

The bias targets are monitors only. They do not automatically become gates after
a deployment change; that requires an explicit implementation and policy change.
