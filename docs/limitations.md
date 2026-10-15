# Known limitations and next evidence

Source review date: 2026-10-10. These limits remain visible even when local
tests or configured scorecard thresholds pass.

| Area | Current limit | Useful next evidence / change |
|---|---|---|
| Human agreement | Template exists; completed human labels and report do not | 20 human-scored answers matched to the exact run; inspect agreement and disagreements |
| Position bias | Historical flip rate 0.2667 exceeds target <0.10 | Fresh comparisons with a verified distinct judge model and enough cases to assess variation |
| Self-preference | Guard compares deployment names; the historical evaluation explicitly allowed same-deployment judging | Verify underlying model identity; record the override and model versions in artifacts |
| Bias enforcement | Derived metrics are displayed separately from `evaluate_gate` | Deliberately implement and validate bias gates; changing judge deployment alone does not activate them |
| Coverage | 30 RAG cases and 6 trajectory cases; small corpus derived from test contexts | Independent cases and corpus, broader failure cases, and a held-out split |
| Trajectories | Reported tool names, not independently reconstructed traces; `rag_qa` has no trajectory expectations | Trusted capture and explicit coverage checks; separate runtime authorization |
| Step limits | Pure evaluator computes `max_steps_exceeded`, but adapter does not emit it as a `Score` | Add adapter coverage before claiming this appears in reports |
| Partial errors | Means exclude `None`; partial failures can pass. Judge errors use a separate metric; failed pairwise outputs omit a flip score | Define minimum metric coverage and evaluator error policies |
| Judge retries | Rubric validation can issue a third request whose response is not validated; API exceptions can abort evaluation | Correct retry accounting and test malformed-output and API-failure paths |
| Calibration inputs | Loader checks a minimum label count but not score bounds or unique IDs; matched count can be smaller | Validate 1–5 ratings, uniqueness, matched cases and run provenance |
| Cost | Stored run total excludes evaluator calls; unknown-price calls contribute no known dollars | Instrument evaluator spend and make incomplete totals explicit |
| Artifacts | Baseline stores means/metadata, not raw scores, dataset hash or run timestamp | Preserve sanitized per-case evidence and provenance for reproducibility |
| CI enforcement | `eval.yml` is now a manual review placeholder with no inference; a failing check is not a protected branch rule | Owner-approved trust and required-check policy, with a plan for paid evaluation |
| Cloud state | Successful workflows are historical; live auth, quota and trace export not rerun | Separate authorized cloud validation with a defined spend limit |

This refresh documents existing evaluator behavior without changing its runtime
semantics, thresholds, baseline, cloud infrastructure. Workflow adoption removes automatic inference and limits the workflow token to contents read; repository permissions and Azure federation are unchanged.
The added offline demo is a deterministic fixture, not new performance evidence.
