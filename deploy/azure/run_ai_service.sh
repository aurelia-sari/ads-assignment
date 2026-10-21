#!/usr/bin/env bash
# systemd runs one existing host service per unit. Local scripts stay unchanged.
set -euo pipefail
cd "$(dirname "$0")/../.."
root=$(pwd)
case "${1:-}" in
  ai-mode) entry=app.py ;;
  mcp-server|rag-server|multi-agent-server) entry=server.py ;;
  *) echo 'Unknown AI service' >&2; exit 2 ;;
esac
cd "$root/ai-services/$1"
exec "$root/ai-services/.venv/bin/python" "$entry"
