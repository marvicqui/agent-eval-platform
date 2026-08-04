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

All three, with precedence: **trajectory (deterministic) > RAG metrics >
judge**. `forbidden_tool_calls > 0` fails the scorecard outright regardless
of any other score.

## Rationale

Each layer covers what the others cannot:

- **Deterministic trajectory checks** are the only *oracle* in the system —
  they cannot be wrong about what they measure. Which tools ran, in what
  order, whether a banned write operation was touched: these are facts from
  the trace. The industry evidence is blunt: the agent deployments that work
  in production (test migration, code transforms) share the property of
  having an oracle. Where an oracle is possible, an LLM opinion is the wrong
  instrument. Hence the precedence rule.
- **RAG metrics (RAGAS)** measure the retrieval pipeline specifically —
  faithfulness and context recall localize *where* a RAG system failed
  (retrieval vs generation), which a single end-to-end judge score cannot.
- **LLM-as-Judge** is the only layer that can grade open-ended technical
  accuracy and actionability. It is also the least trustworthy layer, so it
  ships with measured bias mitigations and human calibration
  (docs/judge-failure-modes.md), and it never overrides the layers below it.

Why not judge-only (the common shortcut): a judge cannot detect that an
agent reached a good answer through a forbidden action, and its absolute
scores drift with model versions. Why not deterministic-only: it cannot
grade whether an explanation of hub-spoke DNS is *correct and actionable* —
the actual substance of these workloads.

## Consequences / trade-offs accepted

- Three layers cost more per run than one. Measured: judge adds 3 calls per
  case (rubric + both-orders pairwise); RAGAS adds ~4. At gpt-5-mini prices
  a full 30-case run stays under a dollar; acceptable for merge-gating.
- The trajectory layer only sees tools the SUT reports (or traces). An
  uninstrumented tool is invisible — mitigated by the contract that every
  tool wears `@traced_tool_call` and SUTs return `tool_calls`.
- RAGAS pins us to its API churn; contained by wrapping it in one module
  (`evaluators/rag.py`) behind the stable Evaluator protocol.
