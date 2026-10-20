#!/usr/bin/env bash
# Full Azure deployment in one command: provision VM -> deploy app -> validate -> save evidence.
set -uo pipefail
cd "$(dirname "$0")"
EVID=../../evidence/cloud
RG=${RG:-nextstop-rg}
VM=${VM:-nextstop-vm}
mkdir -p "$EVID"

# 1. Infrastructure (shows progress live, keeps the output to read VM_HOST)
OUT=$(bash provision.sh | tee /dev/stderr) || { echo "provision.sh failed" >&2; exit 1; }
VM_HOST=$(echo "$OUT" | grep '^VM_HOST=' | tail -1 | cut -d= -f2)
[ -n "$VM_HOST" ] || { echo "Could not read VM_HOST" >&2; exit 1; }
export VM_HOST

# 2. Application
bash deploy.sh || { echo "deploy.sh failed" >&2; exit 1; }

# 3. Validation (keep going afterwards so the evidence is still saved)
bash smoke_cloud.sh | tee "$EVID/smoke_cloud_output.txt"
status=${PIPESTATUS[0]}

# 4. Infrastructure evidence for the report (best effort)
az network nsg rule list -g "$RG" --nsg-name "${VM}NSG" -o table | tee "$EVID/nsg_rules.txt" || true
az vm show -d -g "$RG" -n "$VM" \
  --query '{name:name, ip:publicIps, size:hardwareProfile.vmSize, location:location}' -o table \
  | tee "$EVID/vm_details.txt" || true

echo ">> done: http://$VM_HOST:8080  (smoke test exit code: $status)"
exit "$status"
