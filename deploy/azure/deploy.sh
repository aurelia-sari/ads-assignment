#!/usr/bin/env bash
# Repeatable deploy: copy the repo to the VM and (re)start the compose stack with AI disabled.
set -euo pipefail
: "${VM_HOST:?set VM_HOST to the VM public IP}"
SSH_KEY=${SSH_KEY:-$HOME/.ssh/nextstop_deploy}
REMOTE="azureuser@$VM_HOST"
SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=accept-new"
cd "$(dirname "$0")/../.."

echo ">> syncing code to $REMOTE"
rsync -az --delete -e "ssh $SSH_OPTS" \
  --exclude .git --exclude .venv --exclude __pycache__ --exclude '*.pyc' \
  --exclude node_modules --exclude ai-services --exclude docs \
  ./ "$REMOTE:~/nextstop/"

echo ">> starting stack (AI-Mode, MCP, RAG, Multi-Agent disabled)"
ssh $SSH_OPTS "$REMOTE" "
  set -e
  dpkg -s python3-requests >/dev/null 2>&1 || sudo apt-get install -y -q python3-requests
  cd ~/nextstop
  AI_MODE_ENABLED=false MCP_ENABLED=false RAG_ENABLED=false MULTI_AGENT_ENABLED=false \
  PUBLIC_BASE_URL=http://$VM_HOST:8080 \
  docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d --build --remove-orphans
  docker compose -f docker-compose.yml -f docker-compose.cloud.yml ps
"
echo ">> deployed: http://$VM_HOST"
