# ADR-0001: Instrument with OpenTelemetry GenAI conventions, not the Langfuse SDK

- **Status:** accepted
- **Date:** 2026-08-03
- **Phase:** 1

## Context

Every LLM call, tool call and agent run in this platform (and in the four
downstream portfolio projects) must emit traces with model, tokens, latency
and cost. Langfuse Cloud is the chosen backend. There are two ways to feed it:

1. **Langfuse's own Python SDK** (`langfuse` package, `@observe` decorator) —
   richer Langfuse-specific features (prompt management, scores API, sessions).
2. **Plain OpenTelemetry** with the [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/),
   exported over OTLP/HTTP to Langfuse's OTLP endpoint.

## Decision

Plain OpenTelemetry. The Langfuse SDK is not a dependency of this project.

## Rationale

- **Migration cost asymmetry.** With OTel, replacing Langfuse Cloud
  (self-hosted Langfuse, Jaeger, Azure Monitor / App Insights) means changing
  one exporter endpoint and one auth header in `src/aep/instrumentation/otel.py`.
  With the vendor SDK it means rewriting every instrumented call site in five
  repositories. The planned self-hosting path (Proxmox) makes this a real
  scenario, not a hypothetical.
- **Neutral schema.** GenAI semantic conventions (`gen_ai.usage.input_tokens`,
  `gen_ai.request.model`, …) are an open spec that any backend can interpret.
  Langfuse explicitly supports ingesting them via OTLP.
- **One less SDK to trust.** The instrumentation layer is part of what this
  platform *evaluates* (cost per request is a first-class metric). Computing
  cost ourselves from a reviewed price table beats trusting a vendor's opaque
  cost model — and when both are visible, disagreement between them is signal.

## Consequences / trade-offs accepted

- Langfuse-specific features (prompt management, datasets UI, scores API) are
  not available through OTLP. Scores and calibration live in this repo as
  code and committed artifacts instead — which is what makes them reviewable
  in PRs anyway.
- Cost is client-side and depends on the price table in `src/aep/config.py`
  staying current. Mitigation: unknown models are flagged
  `aep.usage.cost_unknown=true` rather than priced at $0, so a stale table is
  visible in traces instead of silently wrong.
- The OTel SDK's batch exporter must be flushed explicitly in short-lived
  processes (`aep.instrumentation.flush()`), a footgun the vendor SDK hides.
  Accepted and documented in the module docstring.
