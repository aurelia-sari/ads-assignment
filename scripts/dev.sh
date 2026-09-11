#!/usr/bin/env bash
# Everyday commands for the integrated Group 25 travel application.
#
#   ./scripts/dev.sh up        build and start everything
#   ./scripts/dev.sh down      stop and remove containers and volumes
#   ./scripts/dev.sh health    show the health of every service
#   ./scripts/dev.sh smoke N   run the CRUD smoke test for student N
#   ./scripts/dev.sh loop      run the Plan -> Act -> Observe -> Adapt loop
#   ./scripts/dev.sh logs [service]
#
# The AI services (AI-Mode, MCP, RAG) and the agentic loop are not containerised
# in Release 1. They are managed separately by ./scripts/ai_services.sh, and
# `dev.sh up` starts them for you.

set -euo pipefail

cd "$(dirname "$0")/.."

require_env() {
    if [ ! -f .env ]; then
        echo "No .env found, copying .env.example"
        cp .env.example .env
    fi
}

require_ollama() {
    if ! curl -sf -m 3 http://localhost:11434/api/version > /dev/null; then
        echo "WARNING: Ollama is not responding on localhost:11434."
        echo "         AI-Mode will start but every AI request will fail."
        echo "         Start it with: ollama serve"
    fi
}

require_ai_services() {
    if [ ! -x ai-services/.venv/bin/python ]; then
        echo "Local AI services are not installed yet. Installing..."
        ./scripts/ai_services.sh install
    fi
}

case "${1:-}" in
    up)
        require_env
        require_ollama
        require_ai_services
        # The local AI services come up first: the containerised backends are
        # configured to reach them, so starting them afterwards means the first
        # AI request of every session fails for no good reason.
        ./scripts/ai_services.sh up
        docker compose up --build -d
        echo
        echo "Integrated application: http://localhost:8080"
        echo "Waiting for services to report healthy..."
        python3 scripts/wait_for_health.py 5000 5200 5300 5400 5500 5101 5201 || true
        ;;
    down)
        docker compose down --volumes
        ./scripts/ai_services.sh down
        ;;
    health)
        docker compose ps
        echo
        echo "Local (non-containerised) AI services:"
        ./scripts/ai_services.sh status | sed 's/^/  /'
        echo
        curl -sf http://localhost:5000/health/all | sed 's/<[^>]*>/ /g' | tr -s ' '
        ;;
    smoke)
        python3 scripts/smoke_test.py "${2:-1}"
        ;;
    loop)
        require_ollama
        require_ai_services
        # Runs on the host now, not through compose: Release 1 requires the
        # agentic loop to be non-containerised.
        ( cd ai-services/agentic-loop && exec ../.venv/bin/python main.py "${@:2}" )
        ;;
    logs)
        docker compose logs -f --tail 100 "${2:-}"
        ;;
    *)
        sed -n '2,12p' "$0"
        exit 1
        ;;
esac
