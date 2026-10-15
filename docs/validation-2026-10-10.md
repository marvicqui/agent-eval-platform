# Local validation — 2026-10-10

Validation scope: portfolio documentation refresh and synthetic offline demo,
starting from remote `main` at
`d789e9c1168e369aee46c41b7d9484692a7c8346`.
The source checkout was clean. Work was performed in an independent local clone;
the original checkout and remote repository were not changed.

## Environment and commands

macOS arm64, Python 3.12.13, uv 0.12.1; dependencies installed from the unchanged
`uv.lock`. Package download access was used for installation. No Azure/LLM or
Langfuse service calls were made by validation. Azure, OpenAI, Langfuse, AEP and
OTel environment variables were removed from the validation child processes.
No `.env` or existing run artifacts were copied into the working clone.

| Command | Observed result |
|---|---|
| `uv sync --frozen --dev --no-editable` | Locked dependency installation completed; subsequent offline sync passed |
| `uv run --offline --frozen --no-editable pytest tests/ -v` | **49 passed**, 0.46 s reported by pytest |
| `uv run --offline --frozen --no-editable ruff check src/ tests/ examples/` | All checks passed |
| `uv run --offline --frozen --no-editable mypy src/` | No issues in 26 source files |
| `uv run --offline --frozen --no-editable aep dataset stats rag_qa` | 30 cases across 6 categories and 3 difficulty levels |
| `uv run --offline --frozen --no-editable aep dataset stats agent_tasks` | 6 cases |
| `uv run --offline --frozen --no-editable python -m examples.offline_demo` | Expected PASS and FAIL; process exit 0 |
| `uv run --offline --frozen --no-editable aep --help` | CLI entry point loaded successfully |

Demo output:

```text
SYNTHETIC trajectory demo: no tools executed; no model quality measured.
Gate scope: forbidden-tool hard rule only, no RAG thresholds or baseline.
allowed: PASS; tools=['retrieve']
forbidden: FAIL (expected); tools=['retrieve', 'delete_resource']
  forbidden_tool_calls: HARD FAIL: 1 forbidden tool call(s) in at least one case — overrides every other metric
Demo verified: a reported forbidden call overrides all other scores.
```

The first editable installation exposed a host-specific failure: macOS hidden
flags on `.pth` files caused Python to ignore the installed source path and
raise `ModuleNotFoundError: aep`. Clearing the flag was not durable in this
workspace. The documented `--no-editable` installation and execution mode
resolved the import failure without changing package source or dependencies.
The first fully offline installation attempt also lacked cached wheels;
allowing the locked package downloads resolved that setup prerequisite.

## Historical cloud evidence, observed on 2026-10-10

| Evidence | Date / scope |
|---|---|
| [Latest CI success](https://github.com/marvicqui/agent-eval-platform/actions/runs/30893874232) | 2026-08-04, `d789e9c...`, push to `main` |
| [Latest observed successful eval](https://github.com/marvicqui/agent-eval-platform/actions/runs/30889826206) | 2026-08-04, `0177b40...`, pull request event |
| [Committed baseline](../evals/baseline.json) | Last modified by `87a20419...` on 2026-08-04; 30 RAG cases |

These are historical runs at their recorded commits, not current validation of
this proposed patch. The branch API reported `main` as unprotected; no branch
rules or permissions were changed. Baseline metrics and thresholds are unchanged.

## Not validated or completed

- New Azure model inference, authentication, model availability or quota.
- Langfuse export or any current Azure resource/RBAC state.
- A fresh RAGAS or LLM-judge evaluation, complete evaluator cost, or model-quality improvement.
- Human calibration: the existing 20-case template is still unscored.
- Hosted CI for this patch, merge protection or downstream project integration.
- Production readiness or a security audit of dependencies and infrastructure.

The offline tests establish deterministic behavior on their fixtures only.
See [testing scope](testing.md), [metric interpretation](metrics.md) and
[known limitations](limitations.md) before using the historical scores.
