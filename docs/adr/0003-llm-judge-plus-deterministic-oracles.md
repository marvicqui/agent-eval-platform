# ADR-0003: Three evaluator layers, with deterministic checks outranking the judge

- **Status:** accepted
- **Date:** 2026-08-04
- **Phase:** 3

## Context

"How do you test a non-deterministic system?" is the question this platform
exists to answer. The candidate evaluation approaches:

1. Only deterministic checks (string/regex/trajectory asserts)
2. Only statistical RAG metrics (RAGAS)
3. Only LLM-as-Judge
4. All three, layered, with an explicit precedence

## Decision

All three, with a deterministic forbidden-tool veto. RAG and judge quality
floors are both checked; neither quality score overrides the other.
`forbidden_tool_calls > 0` fails the scorecard regardless of other scores.

## Rationale

Each layer covers what the others cannot:

- **Deterministic trajectory checks** are the only *oracle* in the system —
  their output is reproducible for a given reported tool list. Which tools
  ran, and in what order, is supplied by the SUT, not reconstructed from OTLP
  traces. The checker cannot establish that the reported list is complete. Checking
  these explicit constraints in code avoids delegating factual comparisons
  to a probabilistic judge.
- **RAG metrics (RAGAS)** measure the retrieval pipeline specifically —
  faithfulness and context recall localize *where* a RAG system failed
  (retrieval vs generation), which a single end-to-end judge score cannot.
- **LLM-as-Judge** is the only layer that can grade open-ended technical
  accuracy and actionability. It is also the least trustworthy layer, so it
  ships with bias monitors and human calibration tooling
  ([failure modes](../judge-failure-modes.md)). Completed human calibration
  is pending; a high judge score never overrides a forbidden-tool violation.

Why not judge-only (the common shortcut): a judge cannot detect that an
agent reached a good answer through a forbidden action, and its absolute
scores drift with model versions. Why not deterministic-only: it cannot
grade whether an explanation of hub-spoke DNS is *correct and actionable* —
the actual substance of these workloads.

## Consequences / trade-offs accepted

- Three layers cost more per run than one. The judge normally adds three
  requests per case (rubric + both-orders pairwise), with extra requests on invalid
  rubric output. RAGAS request counts depend on the metrics and responses.
  No complete evaluator-inclusive cost is established by the SUT cost total.
- The trajectory layer only sees `SUTResult.tool_calls`. Trace decorators
  improve observability but do not independently populate or audit this list.
  The checker is an after-the-fact evaluation, not a runtime authorization layer.
- RAGAS pins us to its API churn; contained by wrapping it in one module
  (`evaluators/rag.py`) behind the stable Evaluator protocol.

## Implementation review — 2026-10-10

The decision remains historical; these clarifications describe current code.
See [architecture](../architecture.md) and [limitations](../limitations.md).
