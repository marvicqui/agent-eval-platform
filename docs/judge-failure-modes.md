# LLM-as-Judge failure modes and what this platform does about them

An LLM judge is the only scalable way to grade open-ended answers, and it is
also a measurement instrument with known, reproducible defects. This platform
treats each documented bias as an engineering requirement: mitigate it in
code, and — more importantly — **measure whether the mitigation works**.
Implementation: `src/aep/evaluators/judge.py`. Machinery tests (synthetic
biased judges): `tests/test_bias_mitigation.py`. Real-model numbers: the
scorecard and `aep calibrate`.

## 1. Position bias

**What it is.** In pairwise comparisons, judges systematically prefer the
answer presented first (sometimes last, depending on the model). Reported
across judge papers since Zheng et al. 2023 ("Judging LLM-as-a-Judge with
MT-Bench"); it does not disappear just because models got better.

**Mitigation implemented.** Every pairwise comparison runs twice, with the
answers in both orders. If the verdict changes with the order, the judge was
answering "which came first?" — the comparison counts as a **tie** and the
flip is recorded.

**How we know it works.** `position_flip_rate` is a first-class run metric
(target < 10%). A synthetic always-prefers-first judge is caught by the unit
tests; the real judge's flip rate is measured on every eval run via the
answer-vs-reference comparison. Cost of the mitigation: 2x judge calls per
comparison — the price of not fooling ourselves.

## 2. Verbosity bias

**What it is.** Judges reward length. Longer answers correlate with higher
scores even when the extra text adds nothing — a direct incentive for bloated
agents if unchecked.

**Mitigation implemented.** The rubric's completeness criterion scores
**coverage of the case's `required_points`**, an enumerated list, never
length or thoroughness in the abstract. The prompt states explicitly that
length itself is not quality.

**How we know it works.** Answer length is recorded per case, and the
scorecard reports `verbosity_correlation` — Pearson r between judge score
and answer length across the run (target |r| < 0.3). A high r with a
coverage-based rubric would mean the mitigation failed; the number makes
that visible instead of assumed. Note the honest caveat: some positive
correlation is legitimate (complete answers are somewhat longer), which is
why the target is a band, not zero.

## 3. Self-preference bias

**What it is.** Judges score outputs from their own model family higher than
outputs of comparable quality from other families.

**Mitigation implemented.** `check_self_preference_guard` refuses to build a
judge whose deployment equals the SUT's deployment. The override
(`AEP_ALLOW_SAME_JUDGE=1`) exists because this project currently has quota
for exactly one chat model (gpt-5-mini; gpt-large pending an Azure quota
increase) — but it is an explicit, visible configuration choice, and any
report produced under it carries a known-limitation caveat.

**How we know it works.** A unit test asserts the guard trips on equal
deployments and passes on distinct ones. The residual risk while the
override is active is documented rather than hidden: judge scores may be
inflated in absolute terms; regression *deltas* (same judge, same bias, two
points in time) remain meaningful, which is what the CI gate actually uses.

## 4. The failure mode that subsumes the others: unvalidated trust

Every mitigation above still assumes the judge broadly tracks human
judgment. That assumption is tested directly: `aep calibrate` compares the
judge against 20 human-annotated cases (Spearman correlation + Cohen's
kappa) and reports where the disagreements concentrate. A judge that cannot
demonstrate correlation with its owner's judgment is decoration, not
measurement.

Also in this category: **malformed output**. The judge must return JSON that
validates against a pydantic schema; one retry with the validation error in
context, then the case is marked `judge_error` (missing data) rather than
being scored 0 or silently dropped — an evaluator failure must never
masquerade as a quality signal.
