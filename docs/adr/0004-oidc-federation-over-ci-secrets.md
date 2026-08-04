# ADR-0004: GitHub Actions authenticates to Azure via OIDC federation, not stored secrets

- **Status:** accepted
- **Date:** 2026-08-04
- **Phase:** 5

## Context

The eval workflow must call Azure OpenAI on every pull request. That
requires an identity. The traditional approach stores a service principal
secret (client secret or certificate) in GitHub Secrets; the alternative is
workload identity federation: GitHub's OIDC provider issues a short-lived
token per job, Azure trusts specific `repo:owner/name:...` subjects, and no
credential is ever stored anywhere.

## Decision

OIDC federation. App registration `gha-agent-eval-platform` with two
federated credentials (`ref:refs/heads/main` and `pull_request`), and a
single role assignment: **Cognitive Services OpenAI User, scoped to the one
Foundry resource** — not Contributor, not subscription scope.

## Rationale

- **Nothing to leak, rotate or expire.** A stored SP secret in a public
  repo's CI is the classic breach path; a federated token lives minutes and
  only materializes inside a job run from this exact repo. This is the same
  short-lived, single-hop token principle applied to agent identity.
- **Blast radius by scope.** The identity can call one model endpoint. It
  cannot deploy, read state, or touch any other resource — a compromised
  workflow gets inference access and nothing else. This mirrors the
  platform's own `forbidden_tool_calls` philosophy at the infrastructure
  layer.
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
  Both paths converge on `DefaultAzureCredential`, and preflight checks the
  deployments are reachable, which catches drift at run start.
- The federation subjects pin this exact repo path; a fork's PRs get tokens
  for *their* repo subject, which Azure does not trust — fork PRs simply
  cannot run the eval job (CI still runs; it needs no cloud). Accepted:
  that is the correct security posture for a public repo.
