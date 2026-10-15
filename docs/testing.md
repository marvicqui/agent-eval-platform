# Local tests and what they establish

Use Python 3.12 and uv from the repository root. Keep the lockfile unchanged:

```bash
uv sync --frozen --dev --no-editable
uv run --offline --frozen --no-editable pytest tests/ -v
uv run --offline --frozen --no-editable ruff check src/ tests/ examples/
uv run --offline --frozen --no-editable mypy src/
uv run --offline --frozen --no-editable aep dataset stats rag_qa
uv run --offline --frozen --no-editable aep dataset stats agent_tasks
uv run --offline --frozen --no-editable python -m examples.offline_demo
```

The initial sync needs access to package downloads or a populated uv cache.
`--offline` prevents uv fetching packages; it is not a network sandbox for
arbitrary Python code. The commands listed above use local data and synthetic
clients and do not initialize the online SUT or trace exporter. No `.env` is
needed. `--no-editable` installs a package snapshot rather than depending on an
editable `.pth` path. On the validation macOS host, hidden `.pth` files were
ignored by Python; this mode avoided that host-specific import failure. Keep
`--no-editable` on `uv run` too, so uv does not restore an editable install.
After source edits, refresh the package with
`uv sync --frozen --dev --no-editable --reinstall-package aep`.

`make test` and `make lint` remain existing convenience targets; the explicit
commands above preserve the validated installation mode and frozen lockfile.

## Coverage

| Test file | What it validates |
|---|---|
| `test_dataset_schema.py` | Invalid JSON, unknown fields, duplicate IDs, empty datasets and committed dataset coverage |
| `test_trajectory.py` | Required/forbidden tools, precision/recall, repeated patterns, step count and ordering |
| `test_bias_mitigation.py` | Both-order comparison using scripted clients, deployment-name guard and Pearson arithmetic |
| `test_offline_boundary.py` | Socket connection and helper calls are rejected by the autouse fixture |
| `test_thresholds.py` | Forbidden-tool veto, metric floors, missing metrics, regression tolerance and aggregation |

The demo exercises the real trajectory adapter, aggregation and hard gate on
two synthetic lists. Its expected negative case prints `FAIL (expected)` while
the script exits 0 when both outcomes match expectations. It bypasses the normal
RAG thresholds, and does not create an evaluation baseline or scorecard file.

Passing these checks does not establish live Azure authentication, RAGAS model
compatibility, Langfuse export, calibrated judge quality, runtime containment,
or complete end-to-end coverage. The existing suite does not directly test the
online runner's retries, calibration input validation, or cloud integrations.

## Online and artifact-based validation

Follow [online setup](quickstart-online.md) only when model usage is intended.
`aep run` executes and evaluates; the quality gate is a separate `aep report`
step. `aep run` can exit 0 even if a subsequent report fails a threshold.

```bash
uv run --offline --frozen --no-editable aep report --run-file evals/runs/latest.json
```

The report command needs a real run artifact with per-case `scores`.
`evals/baseline.json` contains aggregates and cannot replace that artifact.
For a valid scored artifact, exit 0 means the gate passed and exit 1 means
it failed. Exit 2 is used for a missing file or no scores. Malformed JSON or
invalid score schemas can raise an uncaught exception instead. Inspect both
the message and exit status. Partial evaluator errors can still leave a passing
gate, so review sample counts and failures too.

Do not use `--update-baseline` during a demo. It writes the baseline even when
the current gate fails; accepting a new reference is a separate review decision.

Current results are recorded in [validation-2026-10-10.md](validation-2026-10-10.md).
