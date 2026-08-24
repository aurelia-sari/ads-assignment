#!/usr/bin/env bash
# Everyday commands for the integrated Group 25 travel application.
#
#   ./scripts/dev.sh up        build and start everything
#   ./scripts/dev.sh down      stop and remove containers and volumes
#   ./scripts/dev.sh health    show the health of every service
#   ./scripts/dev.sh smoke N   run the CRUD smoke test for student N
#   ./scripts/dev.sh loop      run the Plan -> Act -> Observe -> Adapt loop
#   ./scripts/dev.sh logs [service]

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

case "${1:-}" in
    up)
        require_env
        require_ollama
        docker compose up --build -d
        echo
        echo "Integrated application: http://localhost:8080"
        echo "Waiting for services to report healthy..."
        python3 scripts/wait_for_health.py 5000 5200 5300 5101 5201 || true
        ;;
    down)
        docker compose down --volumes
        ;;
    health)
        docker compose ps
        echo
        curl -sf http://localhost:5000/health/all | sed 's/<[^>]*>/ /g' | tr -s ' '
        ;;
    smoke)
        python3 scripts/smoke_test.py "${2:-1}"
        ;;
    loop)
        require_ollama
        docker compose run --rm agentic-loop "${@:2}"
        ;;
    logs)
        docker compose logs -f --tail 100 "${2:-}"
        ;;
    *)
        sed -n '2,12p' "$0"
        exit 1
        ;;
esac
