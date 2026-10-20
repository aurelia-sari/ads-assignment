#!/usr/bin/env bash
# One-time infrastructure for NextStop. Safe to re-run: never recreates an existing VM.
set -uo pipefail

RG=${RG:-nextstop-rg}
VM=${VM:-nextstop-vm}
KEY=${KEY:-$HOME/.ssh/nextstop_deploy.pub}
HERE="$(cd "$(dirname "$0")" && pwd)"

vm_ip() { az vm show -d -g "$RG" -n "$VM" --query publicIps -o tsv; }

# Open the app ports (80 and 8080-8085). Same rule names on re-run = update, not duplicate.
ensure_ports() {
  echo ">> ensuring network rules (80, 8080-8085)"
  az network nsg rule create -g "$RG" --nsg-name "${VM}NSG" -n open-port-80 \
    --priority 1010 --direction Inbound --access Allow --protocol '*' \
    --destination-port-ranges 80 -o none
  az network nsg rule create -g "$RG" --nsg-name "${VM}NSG" -n open-port-8080-8085 \
    --priority 1020 --direction Inbound --access Allow --protocol '*' \
    --destination-port-ranges 8080-8085 -o none
}

if az vm show -g "$RG" -n "$VM" -o none 2>/dev/null; then
  echo "VM already exists, nothing to create."
  ensure_ports
  echo "VM_HOST=$(vm_ip)"
  exit 0
fi

try_create() {
  local loc="$1" size="$2"
  echo ">> trying $loc / $size"
  az group create -n "$RG" -l "$loc" -o none || return 1
  az vm create -g "$RG" -n "$VM" --image Ubuntu2204 --size "$size" \
    --admin-username azureuser --ssh-key-values "$KEY" \
    --custom-data "$HERE/cloud-init.yml" --public-ip-sku Standard \
    --os-disk-size-gb 64 -o none
}

for loc in eastasia southeastasia australiaeast uksouth swedencentral; do
  for size in Standard_B2s_v2 Standard_B2as_v2 Standard_B2s; do
    if try_create "$loc" "$size"; then
      ensure_ports
      echo "VM_HOST=$(vm_ip)"
      exit 0
    fi
    # Only clean up if no VM was created.
    if az vm show -g "$RG" -n "$VM" -o none 2>/dev/null; then
      echo "VM exists, stopping."
      ensure_ports
      echo "VM_HOST=$(vm_ip)"
      exit 0
    fi
    az group delete -n "$RG" --yes
    sleep 5
  done
done

echo "No region/size combination worked" >&2
exit 1