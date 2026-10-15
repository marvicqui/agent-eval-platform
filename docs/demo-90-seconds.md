# A 90-second demo: evaluation as cloud engineering

Audience: cloud architecture, platform engineering and applied AI reviewers.
Prepare the environment with `uv sync --frozen --dev --no-editable` before recording. Open the
README architecture diagram and `evals/baseline.json`. Use a clean terminal with
no credentials or customer material visible. This script needs no cloud access.

| Time | Show | Say |
|---|---|---|
| 0–15 s | README introduction | “This is an applied AI lab for Azure architecture answers. A prompt can sound better and still become less reliable. I want changes to produce evidence a reviewer can inspect.” |
| 15–30 s | Architecture diagram | “Questions go through a small system under test. Its answers, retrieved context and reported tool calls feed separate evaluators. The scorecard compares quality against versioned thresholds and a baseline.” |
| 30–50 s | `uv run --offline --frozen --no-editable python -m examples.offline_demo` | “These two trajectories are synthetic; no tools or models are called. Retrieval passes. Adding a reported forbidden deletion fails the hard gate. This checks reported behavior after execution; it is not a runtime permission system.” |
| 50–65 s | `uv run --offline --frozen --no-editable pytest tests/ -q` | “The local suite checks dataset integrity, trajectory rules, gate logic and scripted judge biases. It verifies the machinery without cloud credentials.” |
| 65–82 s | Baseline and limitations | “The model numbers shown here are from August 4, 2026. Position flips are about 0.267, above the 0.10 target. Human calibration is pending. The recorded cost is SUT-only, so I do not claim a complete evaluation price.” |
| 82–90 s | ADR links | “The architectural choices are reviewable: versioned datasets, deterministic vetoes, OpenTelemetry and Azure workload identity. The next evidence is human calibration and an authorized fresh cloud evaluation.” |

Expected terminal result: `allowed: PASS`, `forbidden: FAIL (expected)`, and a
successful demo process. Never describe this as a fresh model benchmark.
If pytest takes longer than the slot, show the dated saved test output and name
its date rather than claiming to have just rerun it.

Optional follow-up: open [historical PR #1](https://github.com/marvicqui/agent-eval-platform/pull/1)
to discuss a prompt regression and recovery. Do not start a paid evaluation or
present the old hosted checks as current during the 90-second demo.
