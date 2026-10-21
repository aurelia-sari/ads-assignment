#!/usr/bin/env bash
# Install and supervise the shared AI services on the Azure host (not Docker).
set -euo pipefail
cd "$(dirname "$0")/../.."
root=$(pwd)
units=(nextstop-ai@ai-mode nextstop-ai@mcp-server nextstop-ai@rag-server nextstop-ai@multi-agent-server)

case "${1:-}" in
  stop)
    if [ -f /etc/systemd/system/nextstop-ai@.service ]; then
      sudo systemctl disable --now "${units[@]}"
    fi
    # Only manage Ollama if it was configured by this cloud deployment.
    if [ -f /etc/systemd/system/ollama.service.d/nextstop-cloud.conf ]; then
      sudo systemctl disable --now ollama
    fi
    exit 0
    ;;
  start) ;;
  *) echo 'Usage: configure_ai.sh start|stop' >&2; exit 2 ;;
esac

model=${CLOUD_OLLAMA_MODEL:-llama3.2:latest}
[[ "$model" =~ ^[[:alnum:]][[:alnum:]_.:/-]*$ ]] || { echo 'Invalid model name' >&2; exit 2; }
[[ "$root" =~ ^/[[:alnum:]_./-]+$ ]] || { echo 'Cloud checkout path must not contain spaces or shell characters' >&2; exit 2; }
owner=$(id -un)
state="$HOME/.local/share/nextstop"
mkdir -p "$state/multi-agent"

sudo apt-get update -qq
sudo apt-get install -y -q python3-venv python3-pip curl ca-certificates zstd
bash scripts/ai_services.sh install

if ! command -v ollama >/dev/null 2>&1; then
  installer=$(mktemp)
  trap 'rm -f "$installer"' EXIT
  curl --fail --show-error --silent --location --retry 3 https://ollama.com/install.sh -o "$installer"
  sudo sh "$installer"
  rm -f "$installer"
  trap - EXIT
fi
sudo install -d /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/nextstop-cloud.conf >/dev/null <<'OLLAMA'
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_KEEP_ALIVE=30m"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
OLLAMA
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl restart ollama
ready=false
for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null; then ready=true; break; fi
  sleep 2
done
[ "$ready" = true ] || { echo 'Ollama did not start' >&2; exit 1; }
export OLLAMA_HOST=http://127.0.0.1:11434
# An existing model is kept, avoiding an unnecessary download on each deploy.
ollama show "$model" >/dev/null 2>&1 || ollama pull "$model"

sudo install -d -m 755 /etc/nextstop
sudo tee /etc/nextstop/ai.env >/dev/null <<ENV
PYTHONUNBUFFERED=1
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_MODEL=$model
OLLAMA_REVIEW_MODEL=$model
AI_MODE_URL=http://127.0.0.1:5300
MCP_SERVER_URL=http://127.0.0.1:5400
RAG_SERVER_URL=http://127.0.0.1:5500
MULTI_AGENT_URL=http://127.0.0.1:5600
MULTI_AGENT_ASYNC_ENABLED=true
CLOUD_CITATION_VALIDATION=true
CLOUD_WORKER_TIMEOUT_SECONDS=360
CLOUD_REVIEWER_TIMEOUT_SECONDS=360
SHARED_DB_URL=http://127.0.0.1:5200
STUDENT_1_DB_URL=http://127.0.0.1:5201
STUDENT_2_DB_URL=http://127.0.0.1:5202
STUDENT_3_DB_URL=http://127.0.0.1:5203
STUDENT_4_DB_URL=http://127.0.0.1:5204
STUDENT_5_DB_URL=http://127.0.0.1:5205
MULTI_AGENT_DATA_DIR=$state/multi-agent
ENV
sudo chmod 600 /etc/nextstop/ai.env
sudo tee /etc/systemd/system/nextstop-ai@.service >/dev/null <<UNIT
[Unit]
Description=NextStop shared AI service (%i)
After=network-online.target docker.service ollama.service
Wants=network-online.target

[Service]
Type=simple
User=$owner
WorkingDirectory=$root
EnvironmentFile=/etc/nextstop/ai.env
ExecStart=/bin/bash $root/deploy/azure/run_ai_service.sh %i
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable "${units[@]}"
sudo systemctl restart "${units[@]}"
python3 scripts/wait_for_health.py 5300 5400 5500 5600
# Process health alone is insufficient: warm the configured model and require
# a successful generation before enabling the application paths.
curl --fail --show-error --silent --max-time 240 http://127.0.0.1:5300/model
echo
