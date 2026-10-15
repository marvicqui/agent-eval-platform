# Security and data handling

This public portfolio lab is not a production security boundary. Review is
based on repository code as of 2026-10-10; live Azure RBAC, federation, resources
and service credentials were not inspected or changed in this refresh.

## Credentials and CI trust

- Online Azure clients use `DefaultAzureCredential`; there is no Azure API-key
  setting. The historical evaluation workflow used `azure/login` with OIDC;
  the active manual placeholder performs no Azure login or model calls.
  Online evaluation still needs a reviewed identity and Langfuse configuration.
- ADR-0004 records the intended single-resource inference role. Its current
  assignment must be verified before treating that scope as an operational fact.
- Tenant, subscription and client IDs are identifiers rather than passwords;
  keep unnecessary infrastructure details out of public examples and logs.
- The former `eval.yml` checked out PR code and requested an OIDC token.
  Its replacement is manual-only and requests no OIDC token. Federated identity
  does not make arbitrary PR code trusted. Review actual subject claims, Azure
  trust restrictions, repository settings and available secrets before enabling
  credentialed runs for contributions. Do not switch to privileged PR triggers
  to work around missing credentials. [GitHub OIDC reference](https://docs.github.com/en/actions/reference/security/oidc)
  and [secure workflow guidance](https://docs.github.com/en/actions/reference/security/secure-use)
  describe these boundaries.
- Workflow actions currently use version tags. Immutable action pinning and
  protected evaluation environments are follow-up hardening choices, not
  controls added by this documentation refresh.

## Data destinations

| Artifact / destination | Contents and boundary |
|---|---|
| Azure model endpoint | Online SUT questions and retrieved context; judge prompts also include answers and required points |
| Langfuse OTLP | Decorator spans contain model/token/cost and operation metadata; exceptions may include diagnostic text |
| `evals/runs/*.json` | Answers, contexts, tool names, evaluator rationales and errors; ignored by Git, but still local sensitive-data candidates |
| Annotation files | Questions and generated answers for human review; sanitize before any commit |
| CI logs / scorecard comments | Metrics, costs, timing and failures; review output before publishing |

The current decorators do not explicitly attach complete prompts or answers as
span attributes. That is not a general redaction guarantee for exceptions,
future SUTs or other instrumentation. Use public/synthetic content for this lab;
do not add client names, private documents, personal data or secrets to cases,
screenshots or examples. Tool constraints evaluate what the SUT reports and
cannot prevent a real write/delete operation.

## Local precautions

`.env` and `evals/runs/` are ignored. Ignore rules do not remove already tracked
material or sanitize files. The pre-commit script runs gitleaks if installed
and otherwise warns; a hook file is not automatically activated by cloning.
CI includes a gitleaks action, but a clean scan is not proof that no sensitive
data exists. Run a redacted scan and manually inspect the publication diff.

`scripts/preflight.sh` sources a trusted local `.env` and reads cloud account
state. `scripts/teardown.sh` deletes an Azure resource group. Neither belongs
in the offline quickstart. Offline demo strings such as `delete_resource` are
fixtures; no tool invocation or cloud mutation occurs.
