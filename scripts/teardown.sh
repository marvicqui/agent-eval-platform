#!/usr/bin/env bash
# Teardown: delete ONLY this project's resource group. The shared Foundry
# resource (rg-shared-dev-eus2) is used by four other projects — never touch it.
set -euo pipefail
RG="rg-aep-dev-eus2"
if az group show --name "$RG" >/dev/null 2>&1; then
  echo "Deleting resource group $RG (async)..."
  az group delete --name "$RG" --yes --no-wait
  echo "Deletion requested. Verify later with: az group show --name $RG"
else
  echo "Resource group $RG does not exist — nothing to tear down."
fi
