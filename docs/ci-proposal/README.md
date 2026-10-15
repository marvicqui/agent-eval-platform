# Adopted CI separation — 2026-10-15

The reviewed proposal is now installed at `.github/workflows/ci.yml` and
`.github/workflows/eval.yml`, with the socket guard in `tests/`. Copies under
`files/` retain the original review material; GitHub does not execute that directory.

`ci` / `checks` installs frozen dependencies, runs lint, types, socket-denied unit
tests, a synthetic demo and the existing secret scan. Package downloads and
runner time use their normal resources; no model inference or Azure API call is
part of this workflow. The socket fixture is a regression guard, not a sandbox
for arbitrary contributed code.

The same-path replacement of `eval.yml` removes the automatic `pull_request`
evaluation. It accepts only `workflow_dispatch` and validates a reviewed commit
SHA. Even a manual run performs no Azure login, model call or scorecard comment.
It requests contents read only, with no OIDC or pull-request write permission.
Existing secrets, federation, token scopes and branch rules were not changed.

The bootstrap commit uses `[skip ci]` to suppress push/PR workflows while their
definitions are replaced, before the content commit starts deterministic CI.
See [GitHub's documented skip semantics](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs).
Immutable action pinning and required-check policy remain separate follow-ups.

## Later paid evaluation

No paid evaluation is enabled or authorized by this publication. Before designing
one: identify the exact commit, datasets, model deployments and region; estimate
SUT, judge, RAGAS, embeddings, retries and observability together; agree budget
and stop conditions; complete human calibration and examine position bias;
review effective identity trust. Historical SUT-only cost is not a complete
budget. Concurrency and Azure budget alerts are not hard spending caps.

Only after separate approval should a manual evaluation be designed. Preserve
the run SHA, sample/error counts, full cost scope and scorecard, without relabeling
historical results as a new evaluation. Local verification uses the commands in
[testing.md](../testing.md); never use preflight, Azure login or `make eval` as an offline test.
