#!/usr/bin/env bash
# Run on the VM only; all persistent databases remain in their named volumes.
set -euo pipefail
cd "$(dirname "$0")/../.."
enable_ai=${1:-false}
export CLOUD_OLLAMA_MODEL=${2:-llama3.2:latest}
vm_host=${3:?VM hostname is required}
case "$enable_ai" in true|false) ;; *) echo 'Cloud AI must be true or false' >&2; exit 2 ;; esac
[[ "$vm_host" =~ ^[[:alnum:]][[:alnum:].-]*$ ]] || exit 2
[[ "$CLOUD_OLLAMA_MODEL" =~ ^[[:alnum:]][[:alnum:]_.:/-]*$ ]] || { echo 'Invalid model name' >&2; exit 2; }
compose=(docker compose -f docker-compose.yml -f docker-compose.cloud.yml)
export PUBLIC_BASE_URL="http://$vm_host:8080"
# Always set both directions explicitly: the API containers reach the host;
# configure_ai.sh gives the host processes their loopback URLs separately.
export AI_MODE_URL=http://host.docker.internal:5300
export MCP_SERVER_URL=http://host.docker.internal:5400
export RAG_SERVER_URL=http://host.docker.internal:5500
export MULTI_AGENT_URL=http://host.docker.internal:5600
export AI_MODE_ENABLED="$enable_ai" MCP_ENABLED="$enable_ai"
export RAG_ENABLED="$enable_ai" MULTI_AGENT_ENABLED="$enable_ai"

dpkg -s python3-requests >/dev/null 2>&1 || {
  sudo apt-get update -qq
  sudo apt-get install -y -q python3-requests
}
bash deploy/azure/configure_ai.sh stop
if [ "$enable_ai" = true ]; then
  bash deploy/azure/configure_ai.sh start
fi
"${compose[@]}" up -d --build --remove-orphans
python3 scripts/wait_for_health.py 5000 5200 5101 5102 5103 5104 5105 5201 5202 5203 5204 5205
"${compose[@]}" ps

# Remember a successful selection outside the synchronized checkout. Automatic
# deployments retain this choice; only a manual run changes it explicitly.
selection_dir="$HOME/.local/share/nextstop"
mkdir -p "$selection_dir"
selection_tmp=$(mktemp "$selection_dir/.cloud-ai-selection.XXXXXX")
trap 'rm -f "$selection_tmp"' EXIT
printf '%s\n' "$enable_ai" "$CLOUD_OLLAMA_MODEL" > "$selection_tmp"
chmod 600 "$selection_tmp"
mv "$selection_tmp" "$selection_dir/cloud-ai-selection"
