# ADR-0002: Golden dataset lives in git as JSONL, not in a database

- **Status:** accepted
- **Date:** 2026-08-04
- **Phase:** 2

## Context

The golden dataset is the ground truth every metric is computed against. It
needs storage. The obvious candidates: a database (Langfuse datasets, Azure
Table/Cosmos, SQLite) or plain files in the repository.

## Decision

JSONL files in `datasets/golden/`, versioned in git, one JSON object per
line, validated by a strict pydantic schema at load time.

## Rationale

- **Ground truth changes must be reviewable.** Editing an expected answer
  changes every future metric. As a PR diff, that edit is visible, blamable
  and revertible; as a database UPDATE it is silent. The single most common
  way eval suites rot is unreviewed drift in their ground truth.
- **One history for code and data.** When a metric moves, the question is
  always "did the system change or did the ruler change?" With dataset and
  code in the same history, one `git log` answers it.
- **JSONL, specifically,** because a one-case-per-line format makes diffs
  local (editing case 17 doesn't reformat case 3) and appends trivial.
- **Strict validation compensates for hand-editing.** `extra="forbid"`,
  unique-id checks and per-line error reporting in the loader catch what a
  database schema would have caught, at load time, with line numbers.

## Consequences / trade-offs accepted

- No UI for browsing/editing cases. Accepted: the reviewers of this dataset
  are engineers, and the PR view *is* the UI.
- No concurrent-write story. Irrelevant at this scale (one owner, tens of
  cases).
- Large datasets would bloat the repo. At 30-100 cases of text this is
  kilobytes; if a future project needs thousands of multimodal cases, that
  project gets its own storage decision — this ADR does not claim to scale
  past text datasets a human can review.
- Long JSONL lines are awkward to read raw. Mitigated by `aep dataset stats`
  and by `jq` being universally available.
