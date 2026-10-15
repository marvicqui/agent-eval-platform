> Historical decision: the automatic evaluation described below was replaced
> on 2026-10-15 by a manual review placeholder. No active workflow logs in to
> Azure or requests OIDC. Existing Azure federation was not changed.

# ADR-0004: GitHub Actions authenticates to Azure via OIDC federation, not stored secrets

- **Status:** accepted
- **Date:** 2026-08-04
- **Phase:** 5

## Context

The eval workflow must call Azure OpenAI on every pull request. That
requires an identity. The traditional approach stores a service principal
secret (client secret or certificate) in GitHub Secrets; the alternative is
workload identity federation: GitHub's OIDC provider issues a short-lived
token per job, Azure trusts configured subject claims, and no
long-lived Azure client secret is stored in the workflow. Langfuse credentials
remain stored secrets.

## Decision

Historical configuration (2026-08-04; not revalidated in this refresh):
OIDC federation. App registration `gha-agent-eval-platform` with two
federated credentials (`ref:refs/heads/main` and `pull_request`), and a
single role assignment: **Cognitive Services OpenAI User, scoped to the one
Foundry resource** — not Contributor, not subscription scope.

## Rationale

- **No long-lived Azure client secret to rotate.** A stored SP secret in a public
  repo's CI is the classic breach path; a federated token lives minutes and
  is issued to a job subject to the configured trust conditions. OIDC does
  not itself establish that checked-out PR code is safe. This is the same
  short-lived, single-hop token principle applied to agent identity.
- **Blast radius by scope.** The intended role is scoped to one inference
  resource. Actual permissions depend on the role definition and all assigned
  roles; this ADR is not a current effective-permissions audit.
- **Auditable trust.** The federated subject strings are reviewable
  configuration; who can obtain the identity is defined by repo + ref, not
  by who once saw a secret.

## What stays a secret, what does not

- `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`: real credentials → GitHub
  **Secrets** (Langfuse has no OIDC federation).
- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
  endpoint/resource names: **variables**, visible in logs. They are not
  cryptographic material, but they are reconnaissance information —
  acceptable for a portfolio repo and documented as such in the README; for
  production, put them in secrets to reduce what an attacker learns for
  free.

## Consequences / trade-offs accepted

- Local runs and CI runs authenticate differently (developer identity via
  `az login` vs federated SP), so RBAC drift between the two is possible.
  Both paths converge on `DefaultAzureCredential`. Preflight lists deployments
  but does not prove inference access or validate the Langfuse credentials.
- Review the actual OIDC subject and Azure trust conditions before relying
  on isolation of PR code. Repository identity alone is not a complete
  authorization policy. Credentialed evaluation of external contributions
  needs deliberate trust handling; deterministic CI needs no cloud credentials.

## Implementation review — 2026-10-10

The historical workflow used Azure OIDC and Langfuse secrets. Current Azure RBAC,
federation and resource state were not queried. Follow
[security and data handling](../security.md) before an online run. No workflow,
identity, credential or repository permission is changed by this review.
