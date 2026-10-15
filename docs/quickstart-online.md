# Optional Azure-backed evaluation

This path calls Azure models and exports trace metadata to Langfuse. It can
incur charges. First complete the [local checks](testing.md). No deployment or
credential creation is performed by these instructions.

## Prerequisites

- Python 3.12 environment installed with `uv sync --frozen --dev --no-editable`.
- Existing Azure OpenAI-compatible endpoint and authorized developer identity.
- Chat deployments for SUT and judge, an embeddings deployment, and the RAGAS
  deployment expected by the pinned integration.
- Existing Langfuse project credentials and its regional host.
- Azure CLI, GitHub CLI, Git and jq if using `make preflight`.

Copy the template and fill it locally:

```bash
cp .env.example .env
```

Set `AZURE_OPENAI_ENDPOINT`, `AZURE_AI_RESOURCE`, `AZURE_AI_RG`, the deployment
names and Langfuse fields. Never commit `.env` or paste it into logs. Authenticate
to your intended Azure tenant/subscription explicitly; verify the active account
before any cloud command. `DefaultAzureCredential` may select an identity from
other configured sources, so successful CLI login alone does not prove which
identity the Python client will use.

| Setting | Implementation constraint |
|---|---|
| `AEP_SUT_DEPLOYMENT` | Azure deployment alias used by the example SUT |
| `AEP_JUDGE_DEPLOYMENT` | Equal alias to SUT is rejected unless overridden; different aliases do not prove different underlying models |
| `AEP_ALLOW_SAME_JUDGE` | Set explicitly to `0`; use `1` only when accepting and recording the same-model limitation. Replace the blank template value |
| `AEP_EMBEDDINGS_DEPLOYMENT` | Existing embeddings deployment |
| `AEP_RAGAS_DEPLOYMENT` | In this integration, deployment name must match the underlying model name because RAGAS uses the name for model-specific options |
| `AEP_MAX_CONCURRENCY` | Start conservatively; this caps cases, not a total spend budget |
| `LANGFUSE_HOST` | Correct host for the project region; credentials are still required |

No model availability, quota, price or resource state is certified by the
historical deployment names in this repository.

## Preflight and run

```bash
make preflight
uv run --frozen --no-editable aep run --dataset rag_qa --sut examples.minimal_sut --output evals/runs/latest.json
uv run --offline --frozen --no-editable aep report --run-file evals/runs/latest.json --output evals/runs/scorecard.md
```

Preflight reads CLI auth/account state, lists Azure deployments and checks that
Langfuse key variables are present. It sources `.env` as shell input: use only
your own trusted file. It does not validate the keys with Langfuse, prove model
inference access, check the selected model names, or estimate total cost.

Expected artifacts are a run JSON and Markdown report under ignored
`evals/runs/`. Review them for sensitive content before sharing. The JSON
`total_cost_usd` only covers instrumented SUT calls; evaluator spend is excluded.
Do not interpret it as the total Azure charge. Do not run `make teardown` as a
cleanup step for local tests: it deletes an Azure resource group.

## Human calibration — still pending

The committed annotation sheet and template are historical inputs. Use the
matching scored run artifact for those answers; its aggregate baseline is not
enough. If that artifact is unavailable, retain the historical sheet and use a
new authorized model run to generate a new matching set deliberately:

```bash
uv run --offline --frozen --no-editable aep calibrate --run-file evals/runs/latest.json --make-template --sample 20
```

This replaces the annotation sheet and template. A person must score the exact
answers 1–5 and save `evals/calibration/human_labels.jsonl`. The template zeros
are placeholders, not valid ratings. Check unique case IDs, score range, and
at least 20 matched cases manually: current validation does not enforce all of
these conditions. Then run:

```bash
uv run --offline --frozen --no-editable aep calibrate --run-file evals/runs/latest.json
```

Review the matched count, Spearman correlation, linear-weighted kappa and largest
disagreements in `evals/calibration/report.md`. No model-generated substitute
labels or human-agreement numbers are provided by this portfolio refresh.
