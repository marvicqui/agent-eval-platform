# Golden datasets

The golden dataset is the platform's source of truth: every metric this
project reports is computed against these cases. Treat edits to these files
with the same care as code.

## Why the dataset lives in git (and not a database)

- **Reviewable**: a new case or a changed expected answer shows up as a PR
  diff a human can approve. Silent ground-truth drift is the failure mode
  this prevents.
- **Versioned with the code**: a metric regression can be traced to either a
  code change or a dataset change, because both share one history.
- **Diffable baselines**: `evals/baseline.json` stores aggregate means and dataset metadata.
  Per-case IDs live in the dataset and run artifacts; the baseline does not
  preserve raw scores or case-level provenance.

See ADR-0002 for the full reasoning.

## Files

| File | What it holds |
|---|---|
| `rag_qa.jsonl` | 30 Azure Well-Architected / CAF question-answer cases with ground-truth contexts for RAG metrics |
| `agent_tasks.jsonl` | Agent tasks with trajectory expectations (required/forbidden tools) for the deterministic oracle |

## What makes a good case

1. **The answer is checkable.** `expected.required_points` lists the discrete
   facts a correct answer must cover. The judge scores coverage of these
   points — never answer length. A case whose correctness you cannot enumerate
   does not belong here.
2. **Every fact has a source.** `expected.source` links the authoritative doc
   (Microsoft Learn). If you cannot cite it, you cannot golden it.
3. **`context` is the ground truth for retrieval**, not whatever the SUT
   happened to retrieve. The current RAGAS context-recall call compares retrieved chunks against
   the reference answer; the dataset contexts also supply the example corpus.
4. **Difficulty is about reasoning, not obscurity.** `basic` = single fact,
   `intermediate` = compare/contrast or multi-fact, `advanced` = scenario
   requiring composition of several facts or a trade-off.
5. **Trajectory expectations are conservative.** `forbidden_tools` should list
   every write-capable tool the SUT exposes; a violation is a hard scorecard
   failure by design.

## Adding a case

1. Append one JSON line to the right file (schema: `src/aep/dataset/schema.py`;
   ids are kebab-case and unique across the file).
2. Run `uv run aep dataset stats <file-stem>` — the loader validates every
   line and fails with line numbers on any problem.
3. Review the diff. The credentialed PR workflow currently runs only `rag_qa`;
   adding an `agent_tasks` case does not automatically add it to that workflow.
   A baseline comparison measures aggregate changes; it does not flag added
   case IDs or enforce dataset provenance.
