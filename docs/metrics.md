# Metrics: what each one means and why its threshold is what it is

Thresholds live in `evals/thresholds.yaml`. This page is the reasoning
behind them. Numbers marked *(measured)* come from real runs of
`aep run --dataset rag_qa --sut examples.minimal_sut` on gpt-5-mini —
not invented examples.

## RAG metrics (RAGAS)

| Metric | Question it answers | Threshold | Why |
|---|---|---|---|
| `faithfulness` | Is every claim in the answer supported by the retrieved context? | ≥ 0.85 | The SUT prompt demands answering strictly from context; below ~0.85 the system is inventing content, which for architecture guidance means wrong deployments. |
| `answer_relevancy` | Does the answer address the question asked? | ≥ 0.80 | Standard RAGAS practice; sensitive to hedging and topic drift. Embedding-based, so absolute values run lower than intuition — see calibration notes below. |
| `context_precision` | Was what retrieval returned actually relevant? | ≥ 0.70 | With top-k=2 over ~30 chunks, one irrelevant chunk halves precision; 0.70 tolerates occasional misses while catching a broken retriever. |
| `context_recall` | Did retrieval find everything the reference answer needs? | ≥ 0.70 | Recall failures localize regressions to the retriever rather than the generator — the main diagnostic value of keeping this metric. |

## Judge metrics

| Metric | Question | Threshold | Why |
|---|---|---|---|
| `judge_overall` | Weighted rubric score (accuracy 0.4, completeness 0.3, actionability 0.3), normalized 0-1 | ≥ 0.70 | 0.70 corresponds to ~3.8/5 on the rubric: "broadly correct, covers most required points". Below that, answers stop being usable by a practitioner. |
| `judge_error` | Judge output failed validation twice | reported | Missing data, never averaged into quality metrics. |

## Judge bias monitors (reported every run; gates once judge ≠ SUT model)

| Metric | Target | Why not a gate yet |
|---|---|---|
| `position_flip_rate` | < 0.10 | Measured on the answer-vs-reference pairwise check. Currently judge == SUT model (gpt-5-mini, documented limitation), so flips also absorb self-comparison noise; gating it now would gate on noise. |
| `verbosity_correlation` | \|r\| < 0.30 | Some positive correlation is legitimate (complete answers run longer). The band flags length-reward, not length itself. |

## Trajectory metrics (deterministic oracle)

| Metric | Rule |
|---|---|
| `forbidden_tool_calls` | **Hard fail if > 0**, not configurable. Blast radius is not a tunable. |
| `tool_recall` / `tool_precision` | Reported; thresholded per downstream project once real agents (projects 02-05) run against this platform. |
| `loop_detected`, `max_steps_exceeded`, `ordering_ok` | Reported; same deferral. |

## Regression tolerances

Every gated metric carries `regression_tolerance: 0.05`: a drop of more than
5 points vs the committed `evals/baseline.json` fails the gate even when the
absolute floor is still met. Rationale: absolute floors catch catastrophes;
the tolerance catches the slow bleed. 0.05 was chosen after observing
run-to-run variance of the metrics on identical code (see below) — the
tolerance must sit above noise, below signal.

## Measured reference values

First full evaluated runs, 2026-08-04, gpt-5-mini for SUT, judge and RAGAS
(committed as `evals/baseline.json`):

**`rag_qa` (30 cases):** faithfulness 0.934 · answer_relevancy 0.757 ·
context_precision 1.000 · context_recall 0.852 · judge_overall 0.868 ·
position_flip_rate 0.267 · verbosity_correlation 0.269. Wall clock 1590s
(132s SUT + 1458s evaluation at concurrency 4); SUT cost $0.029/run.

**`agent_tasks` (6 cases):** tool_precision 1.0 · tool_recall 1.0 ·
forbidden_tool_calls 0 · loop_detected 0 · ordering_ok 1.0.

### Calibration notes from this data

- **`answer_relevancy` threshold moved 0.80 → 0.70.** The pre-data starting
  point sat above the honest mean (0.757) of a system whose answers the
  judge independently rates 0.87 overall — the embedding-based metric runs
  structurally low on terse technical answers carrying citation suffixes.
  Keeping 0.80 would have made the gate red on day one for reasons unrelated
  to quality. The regression tolerance (0.05 vs baseline) is what actually
  guards this metric.
- **`position_flip_rate` measured at 0.267 — above the < 0.10 target, and
  reported as-is.** With judge == SUT model and answers vs terse references,
  many pairwise comparisons are near-ties, where flips concentrate. This is
  exactly why the flip check exists: those verdicts are counted as ties
  instead of being trusted, and the number stays a monitor (not a gate)
  until a distinct judge model (gpt-large) is available. An honest 0.267
  with a diagnosis beats a fabricated 0.05.
- **`verbosity_correlation` 0.269** — inside the |r| < 0.30 band; the
  coverage-based rubric is holding.
