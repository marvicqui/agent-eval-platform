#!/usr/bin/env bash
# Preflight: verify everything the platform needs before any code runs.
# Fails loudly and lists exactly what is missing — no silent degradation.
set -euo pipefail
fail=0
need() { command -v "$1" >/dev/null 2>&1 && echo "OK   $1" || { echo "MISS $1"; fail=1; }; }
need az; need gh; need uv; need git; need jq

# Load .env if present so this works out of the box locally (never committed).
if [[ -f .env ]]; then set -a; source .env; set +a; fi

echo "--- auth ---"
gh auth status 2>&1 | head -3 || fail=1
az account show --query "{sub:name, tenant:tenantId}" -o jsonc || fail=1

echo "--- foundry deployments ---"
az cognitiveservices account deployment list \
  --name "${AZURE_AI_RESOURCE:?set AZURE_AI_RESOURCE}" \
  --resource-group "${AZURE_AI_RG:?set AZURE_AI_RG}" \
  -o table || fail=1

echo "--- langfuse ---"
[[ -n "${LANGFUSE_PUBLIC_KEY:-}" && -n "${LANGFUSE_SECRET_KEY:-}" ]] \
  && echo "OK   langfuse keys present" || { echo "MISS langfuse keys"; fail=1; }

exit $fail
