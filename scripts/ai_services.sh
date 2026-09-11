#!/usr/bin/env bash
# Start and stop the Release 1 local AI services.
#
# Release 1 requires AI-Mode, the MCP server and the RAG server to run on the
# host and NOT as docker-compose services, so they are managed here instead of
# by compose. The containerised feature microservices reach them through
# host.docker.internal.
#
#   ./scripts/ai_services.sh up       start all three in the background
#   ./scripts/ai_services.sh down     stop them
#   ./scripts/ai_services.sh status   show whether each is responding
#   ./scripts/ai_services.sh logs ai-mode|mcp-server|rag-server
#   ./scripts/ai_services.sh install  create the venv and install requirements

set -euo pipefail

cd "$(dirname "$0")/.."

VENV="ai-services/.venv"
PYTHON="$VENV/bin/python"
RUNTIME="ai-services/.runtime"

# name:directory:entrypoint:port
SERVICES=(
    "ai-mode:ai-services/ai-mode:app.py:5300"
    "mcp-server:ai-services/mcp-server:server.py:5400"
    "rag-server:ai-services/rag-server:server.py:5500"
)

require_venv() {
    if [ ! -x "$PYTHON" ]; then
        echo "No virtualenv at $VENV. Run: ./scripts/ai_services.sh install"
        exit 1
    fi
}

require_ollama() {
    if ! curl -sf -m 3 http://localhost:11434/api/version > /dev/null; then
        echo "WARNING: Ollama is not responding on localhost:11434."
        echo "         Retrieval still works, but generation will fail."
        echo "         Start it with: ollama serve"
    fi
}

case "${1:-}" in
    install)
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install --quiet --upgrade pip
        for service in "${SERVICES[@]}"; do
            IFS=: read -r name dir _ _ <<< "$service"
            if [ -f "$dir/requirements.txt" ]; then
                echo "installing requirements for $name"
                "$VENV/bin/pip" install --quiet -r "$dir/requirements.txt"
            fi
        done
        "$VENV/bin/pip" install --quiet -r ai-services/agentic-loop/requirements.txt
        echo "Local AI service environment ready."
        ;;

    up)
        require_venv
        require_ollama
        mkdir -p "$RUNTIME"
        # .env holds the CONTAINER-facing spellings, because docker-compose
        # needs them: a backend in a container reaches these services at
        # host.docker.internal. These processes run on the host, where that
        # name does not resolve, so the same three URLs are re-pointed at
        # localhost for our own use. One .env, two perspectives.
        [ -f .env ] && set -a && . ./.env && set +a
        export OLLAMA_BASE_URL="${OLLAMA_BASE_URL_LOCAL:-http://localhost:11434/v1}"
        export AI_MODE_URL="http://localhost:5300"
        export MCP_SERVER_URL="http://localhost:5400"
        export RAG_SERVER_URL="http://localhost:5500"

        for service in "${SERVICES[@]}"; do
            IFS=: read -r name dir entry port <<< "$service"

            if curl -sf -m 2 "http://localhost:$port/health" > /dev/null; then
                echo "$name already running on :$port"
                continue
            fi

            # Run from the service directory so each server's sibling modules
            # import without a package install.
            ( cd "$dir" && exec "../../$PYTHON" "$entry" ) \
                > "$RUNTIME/$name.log" 2>&1 &
            echo $! > "$RUNTIME/$name.pid"
            echo "started $name on :$port (pid $!)"
        done

        echo
        echo "Waiting for the local AI services to respond..."
        for service in "${SERVICES[@]}"; do
            IFS=: read -r name _ _ port <<< "$service"
            for _ in $(seq 1 30); do
                if curl -sf -m 2 "http://localhost:$port/health" > /dev/null; then
                    echo "  $name  ready on :$port"
                    break
                fi
                sleep 0.5
            done
        done
        ;;

    down)
        for service in "${SERVICES[@]}"; do
            IFS=: read -r name _ _ port <<< "$service"
            pidfile="$RUNTIME/$name.pid"
            if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
                kill "$(cat "$pidfile")" 2>/dev/null || true
                echo "stopped $name"
            fi
            rm -f "$pidfile"
        done
        ;;

    status)
        for service in "${SERVICES[@]}"; do
            IFS=: read -r name _ _ port <<< "$service"
            if curl -sf -m 2 "http://localhost:$port/health" > /dev/null; then
                echo "$name  UP    :$port"
            else
                echo "$name  DOWN  :$port"
            fi
        done
        ;;

    logs)
        tail -f "$RUNTIME/${2:-ai-mode}.log"
        ;;

    *)
        sed -n '2,14p' "$0"
        exit 1
        ;;
esac
