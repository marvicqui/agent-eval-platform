# Architecture and implementation boundaries

Reviewed against `d789e9c1168e369aee46c41b7d9484692a7c8346` on 2026-10-10.
This is a local Python evaluation pipeline with an Azure-backed sample SUT.

## Data flow

1. [`dataset/loader.py`](../src/aep/dataset/loader.py) validates JSONL against
   strict Pydantic schemas, rejects duplicate IDs and reports line-level errors.
2. [`runner/executor.py`](../src/aep/runner/executor.py) sends only the question
   to `SystemUnderTest.run`. The semaphore caps concurrent cases. HTTP 429/5xx
   errors receive up to two runner retries; SDK retry behavior is separate.
3. The SUT returns [`SUTResult`](../src/aep/runner/types.py): answer, retrieved
   contexts, and ordered tool names. The minimal example uses a synchronous
   Azure client through `asyncio.to_thread` and retrieves the top two chunks
   from a corpus derived from `rag_qa` contexts and source metadata.
4. [`evaluate_all`](../src/aep/evaluate.py) applies trajectory checks when the
   case defines a trajectory, rubric judging when required points exist, and
   RAGAS when the SUT returns contexts. All evaluator objects are initialized
   before this routing; the CLI does not have a trajectory-only offline mode.
5. [`cli.py`](../src/aep/cli.py) writes the run artifact. `aep report` aggregates
   scores and applies `evals/thresholds.yaml` against the committed baseline.
   This reporting step can use a local artifact without cloud credentials.
6. Decorated SUT calls emit OpenTelemetry spans to Langfuse. Scorecards and
   baseline JSON are separate artifacts; the evaluator does not read OTLP
   spans back to derive trajectories.

## Boundaries that matter

| Boundary | Guarantee | Limit |
|---|---|---|
| Runner → SUT | The public call accepts a question, not expected answers | In-process Python is not a sandbox; a SUT can read local files |
| SUT → trajectory evaluator | Deterministic checks over reported tool names | No independent proof that every executed tool was reported; no runtime prevention |
| Scores → gate | Forbidden calls override scores; configured floors and regressions are checked | Missing trajectory data is not a hard failure by itself; the CI dataset has no trajectory expectations |
| Judge → scorecard | Rubric keys and ranges validated; both-order disagreement recorded | Pairwise ties do not modify `judge_overall`; no human calibration result yet |
| Instrumentation → cost | Token usage priced for decorated SUT calls | Judge/RAGAS cost and unknown prices can make the run total incomplete |
| CI → repository policy | A failed report can produce a failing Actions check | Merge enforcement needs repository rules; it is not implemented by YAML alone |

The runner finishes SUT execution before evaluation. Evaluators run sequentially
within each case, with bounded case-level concurrency. This is not a streaming
evaluation service or a distributed worker queue.

## Decisions and trade-offs

- **JSONL in Git** ([ADR-0002](adr/0002-dataset-in-git-not-database.md)) gives
  reviewable changes at the current 36-case scale. There is no dataset service,
  split management, or independent holdout set.
- **Three evaluator families** ([ADR-0003](adr/0003-llm-judge-plus-deterministic-oracles.md))
  separate factual tool constraints from probabilistic quality signals. The
  implemented precedence is the forbidden-tool veto; RAG and judge floors are
  both enforced, rather than one score overriding the other.
- **OpenTelemetry** ([ADR-0001](adr/0001-opentelemetry-over-vendor-sdk.md)) keeps
  call-site instrumentation separate from Langfuse. The current exporter still
  hardcodes Langfuse's URL path and Basic authentication; another backend needs
  an exporter adaptation, not just an arbitrary host value.
- **Azure OIDC for CI** ([ADR-0004](adr/0004-oidc-federation-over-ci-secrets.md))
  avoids a stored Azure client secret. Trust configuration and RBAC are external
  to this code and need a separate current verification.
- **Small sample SUT** avoids a vector database and embeds the corpus per
  question. It is easy to inspect but does not demonstrate retrieval at scale.

See [limitations](limitations.md), [security](security.md) and the
[dated validation record](validation-2026-10-10.md). No downstream integration
or currently deployed cloud resource is certified by this architecture review.
