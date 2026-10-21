#!/usr/bin/env bash
# Sync the application, then deploy the selected cloud configuration on the VM.
set -euo pipefail
: "${VM_HOST:?set VM_HOST to the VM public IP or hostname}"
ENABLE_CLOUD_AI=${ENABLE_CLOUD_AI:-false}
CLOUD_OLLAMA_MODEL=${CLOUD_OLLAMA_MODEL:-llama3.2:latest}
case "$ENABLE_CLOUD_AI" in true|false) ;; *) echo 'ENABLE_CLOUD_AI must be true or false' >&2; exit 2 ;; esac
[[ "$VM_HOST" =~ ^[[:alnum:]][[:alnum:].-]*$ ]] || { echo 'Invalid VM_HOST' >&2; exit 2; }
[[ "$CLOUD_OLLAMA_MODEL" =~ ^[[:alnum:]][[:alnum:]_.:/-]*$ ]] || { echo 'Invalid model name' >&2; exit 2; }
SSH_KEY=${SSH_KEY:-$HOME/.ssh/nextstop_deploy}
REMOTE="azureuser@$VM_HOST"
SSH_OPTS=(-i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
cd "$(dirname "$0")/../.."

echo '>> waiting for VM first-boot setup (Docker install)'
ready=false
for i in $(seq 1 30); do
  if ssh "${SSH_OPTS[@]}" -o ConnectTimeout=10 "$REMOTE" \
      'cloud-init status --wait >/dev/null 2>&1 && docker compose version >/dev/null 2>&1'; then
    ready=true
    break
  fi
  echo "   not ready yet ($i/30)"
  sleep 10
done
if [ "$ready" != true ]; then echo 'VM did not become ready; deployment aborted.' >&2; exit 1; fi

echo ">> syncing code to $REMOTE"
printf -v rsync_ssh 'ssh -i %q -o BatchMode=yes -o StrictHostKeyChecking=accept-new' "$SSH_KEY"
# Exclusions also protect VM-owned state from --delete. Never send a local .env,
# local venv, local databases or local AI runtime into the deployed environment.
rsync -az --delete -e "$rsync_ssh" \
  --exclude .git --exclude .env --exclude .venv --exclude venv \
  --exclude .runtime --exclude __pycache__ --exclude '*.pyc' --exclude '*.db' \
  --exclude '*.db-journal' --exclude .pytest_cache --exclude node_modules \
  --exclude reports --exclude evidence --exclude docs \
  ./ "$REMOTE:~/nextstop/"

printf -v remote_command 'cd ~/nextstop && bash deploy/azure/deploy_remote.sh %q %q %q' \
  "$ENABLE_CLOUD_AI" "$CLOUD_OLLAMA_MODEL" "$VM_HOST"
# Values were validated above and shell-quoted with printf %q for the remote shell.
# shellcheck disable=SC2029
ssh "${SSH_OPTS[@]}" "$REMOTE" "$remote_command"
echo ">> deployed: http://$VM_HOST (cloud AI: $ENABLE_CLOUD_AI)"
