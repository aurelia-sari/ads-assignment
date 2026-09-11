# NextStop - Group 25 Agentic AI Travel Application

41026 Advanced Software Development, Spring 2026 - Release 1.

An integrated Agentic AI travel planning application built as a microservices
architecture. Five students each own a frontend, a backend/API, and a database
microservice; one shared Docker Compose configuration runs the whole thing.

## Team and feature allocation

| Slot | Student | Feature | Frontend | API | Database |
|------|---------|---------|----------|-----|----------|
| student-1 | Caroline Zhou | Trips & Itinerary (day-by-day) + AI chatbot | 8081 | 5101 | 5201 |
| student-2 | Kevin Kim | Sightseeing, attractions, restaurants, recommendations | 8082 | 5102 | 5202 |
| student-3 | Tanishpreet Kour | Travel mate matching | 8083 | 5103 | 5203 |
| student-4 | Aurelia Sari | Authentication, profile, onboarding, dashboard, travel guides | 8084 | 5104 | 5204 |
| student-5 | Aung Ko Khaing | Flights, hotels, car rentals, budget | 8085 | 5105 | 5205 |

Shared containerised services: `shared-frontend` (8080), `shared-api` (5000),
`shared-db` (5200), `mailpit` (8025 web UI / 1025 SMTP).

Shared **local, non-containerised** services (Release 1): `ai-mode` (5300),
`mcp-server` (5400), `rag-server` (5500) and the `agentic-loop`. These are
deliberately *not* docker-compose services - see "Local AI services" below.

> **Directory naming is fixed.** The project specification (section 7.1)
> requires each student's artefacts to live in their designated `student-x/`
> directory, so the directories are `student-1/` .. `student-5/` and the
> workflows are `student-1.yml` .. `student-5.yml`. Do not rename them to
> include owner names - it breaks every build context and workflow path filter,
> and it reads as non-compliant against marking criterion 1. Ownership is
> recorded in the table above, in a header comment in every source file, and on
> each feature page.

## Prerequisites

- Docker Desktop (running)
- Ollama, with an approved model pulled: `ollama pull llama3.2`
- Python 3.11+ (only for the helper scripts; the services run in containers)

## Quick start

```bash
cp .env.example .env
./scripts/ai_services.sh install   # once: venv for the local AI services
./scripts/dev.sh up
open http://localhost:8080
```

`dev.sh up` starts the local AI services, builds every image, starts the
integrated application, and waits for the services to report healthy. The unified home page at
<http://localhost:8080> routes to all five student frontends and shows a live
health panel for every microservice.

Other commands:

```bash
./scripts/dev.sh health      # health of every service, containerised and local
./scripts/dev.sh smoke 1     # CRUD smoke test for student 1
./scripts/dev.sh loop        # the agentic loop, interactive
./scripts/dev.sh logs student-1-api
./scripts/dev.sh down        # stop and remove volumes
```

## Repository structure

```
.
├── .github/workflows/       student-1.yml .. student-5.yml
├── ai-services/             all NON-containerised, run on the host
│   ├── ai-mode/             shared AI-Mode service (Flask, port 5300)
│   ├── mcp-server/          shared MCP server (Flask + JSON-RPC, port 5400)
│   ├── rag-server/          shared RAG server (Flask + BM25, port 5500)
│   │   └── knowledge/       the curated corpus retrieval runs over
│   ├── agentic-loop/        Plan -> Act -> Observe -> Adapt loop (terminal)
│   └── prompts/             prompt engineering artefacts
│       ├── implementation/  prompts the running application uses
│       └── review/          prompts the agentic loop uses
├── docs/
│   ├── diagrams/            architecture diagrams (Mermaid)
│   ├── evidence/            screenshots and run records for the report
│   ├── ADR-001-service-boundaries.md
│   └── technical-report.md  the Release 0 report skeleton
├── scripts/                 dev.sh, ai_services.sh, smoke_test.py, wait_for_health.py
├── shared/                  unified index.html, shared CSS theme, access API, access DB
├── student-1/ .. student-5/ frontend/, api/, db/, tests/ per student
├── docker-compose.yml       one shared configuration for the whole application
└── .env.example
```

Each `student-N/` directory holds that student's three microservices:

```
student-N/
├── frontend/   nginx + HTMX page, shares the team CSS theme
├── api/        Flask backend/API returning HTMX fragments
├── db/         Flask + SQLite database API that owns its schema
└── tests/
```

## Architecture

Request flow for a normal page interaction:

```
Browser -> shared-frontend (nginx, :8080)
        -> student-N-frontend (nginx)
        -> student-N-api (Flask)
        -> student-N-db (Flask + SQLite)
```

Request flow for an AI interaction:

```
Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM
```

Release 1 adds two more, both through the feature's own backend/API and both
crossing the container boundary onto the host:

```
Frontend -> Backend/API -> MCP server -> student-N-db          (tool call)
Frontend -> Backend/API -> RAG server -> AI-Mode -> Ollama     (grounded answer)
                               |
                               +-> BM25 over knowledge/*.md
```

The containerisation boundary matters: everything left of the arrow into an AI
service runs in Docker, and AI-Mode, MCP, RAG and the agentic loop run on the
host.

Two rules the whole team relies on:

1. **Each database service owns its schema.** No service opens another
   service's SQLite file. Cross-feature data is fetched over HTTP from the
   owning database API. In each backend/API, every database call lives in one
   module so this stays checkable.
2. **No service talks to Ollama directly.** Model choice, prompt loading, and
   AI error handling live in `ai-services/ai-mode`.

All five frontends are reachable from one origin because `shared-frontend`
reverse-proxies `/student-N/` and `/api/student-N/`. That means HTMX never
makes a cross-origin request and the group does not need CORS workarounds.

## Local AI services

Release 1 requires AI-Mode, the MCP server, the RAG server and the agentic loop
to run **on the host** and to stay out of `docker-compose.yml`. They are managed
by their own script:

```bash
./scripts/ai_services.sh install   # create ai-services/.venv, install deps
./scripts/ai_services.sh up        # start ai-mode, mcp-server, rag-server
./scripts/ai_services.sh status    # is each one responding?
./scripts/ai_services.sh logs mcp-server
./scripts/ai_services.sh down
```

`dev.sh up` calls `ai_services.sh up` for you, so the usual workflow is
unchanged.

### How the containers reach them

A containerised backend reaches a host service through `host.docker.internal`,
so every `student-N-api` gets:

| Variable | Value |
|----------|-------|
| `AI_MODE_URL` | `http://host.docker.internal:5300` |
| `MCP_SERVER_URL` | `http://host.docker.internal:5400` |
| `RAG_SERVER_URL` | `http://host.docker.internal:5500` |

`.env` holds those container-facing spellings because compose needs them.
`ai_services.sh` re-points the same three at `localhost` for the host processes,
which is the one thing to remember: **one `.env`, two perspectives.** A service
on the host cannot resolve `host.docker.internal`.

### Turning them off

`MCP_ENABLED` and `RAG_ENABLED` default to `true` and are set to `false` in CI.
The integration stays in the image; only the runtime path is skipped, and the
frontend shows a "disabled in this environment" notice. Without this, CI would
wait out a timeout on every AI path, because the host services do not exist on
a runner.

## The shared MCP server

One non-containerised MCP server on **:5400**, used by all five features. It
speaks JSON-RPC (`initialize`, `tools/list`, `tools/call`) at `POST /mcp`, and
also exposes plain `GET /health` and `GET /tools` for terminal validation.

Six read-only tools are registered, one per feature:

| Tool | Owner | Reads from |
|------|-------|-----------|
| `list_trips`, `get_trip_itinerary` | student-1 | `student-1-db` |
| `search_places` | student-2 | `student-2-db` |
| `find_travel_mates` | student-3 | `student-3-db` |
| `lookup_destination_guide` | student-4 | `student-4-db` |
| `search_flights` | student-5 | `student-5-db` |

Four boundaries are enforced on every call, in `mcp-server/boundaries.py`:

1. **read-only** - only GET is ever issued upstream; there is no write path
2. **allowlisted** - the target must be the service the tool declared
3. **schema-checked** - arguments must match the tool's declared input schema
4. **capped** - results are truncated to the tool's row limit

```bash
curl -s localhost:5400/tools | python3 -m json.tool
curl -s -X POST localhost:5400/mcp -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"list_trips","arguments":{"status":"planned"}}}'
```

## The shared RAG server

One non-containerised RAG server on **:5500**, used by all five features.

Retrieval is BM25 over the curated markdown in
`ai-services/rag-server/knowledge/` - no embedding model and no vector store, so
it starts instantly on an 8 GB machine and every citation traces back to term
frequencies in a named file.

Generation goes through AI-Mode, so the rule that only AI-Mode talks to Ollama
still holds.

Every answer carries **source citations** and a **confidence category** of
high, medium or low, computed from retrieval scores rather than asked of the
model - a small local model asked how confident it is answers "high" almost
unconditionally. When nothing clears the relevance floor, the server returns an
**insufficient-context** response and does not call the model at all.

```bash
curl -s localhost:5500/health | python3 -m json.tool
curl -s -X POST localhost:5500/search -H 'Content-Type: application/json' \
  -d '{"question":"How should I split my trip budget?"}'
curl -s -X POST localhost:5500/ask -H 'Content-Type: application/json' \
  -d '{"question":"What is the capital of Peru?"}'   # insufficient context
```

After editing the knowledge base, `POST /reindex` rebuilds without a restart.

## AI-Mode

`ai-mode` wraps Ollama's OpenAI-compatible API. Configure it in `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434/v1` | Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.2:latest` | model the application serves |
| `OLLAMA_REVIEW_MODEL` | `llama3.2:latest` | larger model for the agentic loop |

Ollama runs on the **host** by default, not in a container. On an 8 GB machine
`llama3.1:8b` needs a 6.2 GB working set and thrashes swap, so the serving model
is `llama3.2` (3B, 2.0 GB). `qwen2.5:0.5b` was tried first and is faster, but it
invents figures the data does not contain. Raise the model on a machine with
more RAM:

```bash
ollama pull llama3.1:8b
# then set OLLAMA_MODEL=llama3.1:8b in .env
```

Check the model is actually reachable from inside the container:

```bash
curl http://localhost:5300/model
```

### Running Ollama in a container

If the group would rather containerise the runtime, add a service to
`docker-compose.yml` using the `ollama/ollama` image with a volume for
`/root/.ollama`, set `OLLAMA_BASE_URL=http://ollama:11434/v1`, and pull the
model into the volume once. Expect a multi-gigabyte image pull.

## Seeded accounts

`shared-db` is seeded (via `shared/db/init_db.py`, baked in at build time) with
10 accounts for local sign-in testing, all sharing the password
`Password123!`. `student1` to `student5` are verified and can sign in at
`/student-4/signin.html`. `traveller6` to `traveller10` are left pending
verification. Rebuild and reset the volume to pick up a change here:

```bash
docker compose down -v
docker compose up -d --build shared-db
```

| Email | Password |
|-------|----------|
| student1@example.com | Password123! |
| student2@example.com | Password123! |
| student3@example.com | Password123! |
| student4@example.com | Password123! |
| student5@example.com | Password123! |

## Mailpit (local email testing)

`student-4-api` sends sign-up verification emails through
[Mailpit](https://mailpit.axllent.org/), a fake local SMTP server with a web
UI - nothing is sent to a real inbox in local dev. To check an email a feature
sent:

```bash
open http://localhost:8025
```

Every message `student-4-api` sends (account verification, and any resends)
shows up there instantly, including the verification link. No configuration
is needed, `mailpit` starts with the rest of the stack via `docker compose
up`, and `student-4-api` is already pointed at it (`MAILPIT_HOST=mailpit`,
`MAILPIT_PORT=1025` in `docker-compose.yml`).

This is a Release 0 stand-in. `send_verification_email()` in
`student-4/api/app.py` is the only place a swap to a real provider (e.g.
Resend) needs to happen for a later release.

## The agentic loop

The shared Plan -> Act -> Observe -> Adapt workflow reviews the running
application rather than reasoning about it in the abstract:

- **Plan** - the model proposes up to four checks for the chosen target.
- **Act** - the loop executes them for real: HTTP calls to the live services,
  and reads of `docker-compose.yml`, `shared/nginx.conf`, and the workflow files.
- **Observe** - the model compares its plan against the collected evidence and
  separates confirmed passes from issues.
- **Adapt** - the model names the single highest-value next change and the
  check that would confirm it, which seeds the next iteration.

Review targets: the database microservices, the backend/API implementation, the
microservices architecture, the DevOps pipeline, and - added in Release 1 - the
**MCP server** and **RAG grounding** validation modes.

The MCP mode calls every registered tool, then fires six probes that must each
be refused, checking not only that the call failed but that it was refused at
the boundary that should have caught it. The RAG mode checks retrieval and
grounding separately, because they fail separately: that the top source is the
file which actually contains the answer, that answers carry citations and a
confidence category, and that off-corpus questions are refused rather than
answered.

The loop runs on the host, not in a container.

```bash
./scripts/dev.sh loop            # interactive menu
./scripts/dev.sh loop mcp        # MCP validation mode
./scripts/dev.sh loop rag        # RAG grounding validation mode
./scripts/dev.sh loop all 2      # two iterations over all six targets
```

Every run writes a markdown record to `ai-services/agentic-loop/runs/`. Copy the
run you want to submit into `docs/evidence/` - the technical report has to
include an agentic loop workflow record.

## CI/CD

Each student has a workflow that builds their three microservices, starts them
with the shared compose file, waits for health, and runs the CRUD smoke test:

```bash
python3 scripts/smoke_test.py 1
```

Workflows trigger on pushes to `main` and on pull requests that touch that
student's directory, the shared directories, or the compose file.

## Working on your feature

Students 3 and 5 currently have a generated scaffold: a working `records` CRUD
microservice trio, marked with `TODO` comments. The wiring already works, so
replace it from the bottom up:

1. `student-N/db/init_db.py` - your real schema, seeded with 10+ rows per table
2. `student-N/db/app.py` - CRUD endpoints for your resources
3. `student-N/api/app.py` - HTMX fragments for your feature
4. `student-N/frontend/templates/index.html` - your page, using the shared theme

`student-1/` shows the fuller layout (`routes/`, `services/`, `views/`) to move
to once a feature outgrows a single module.

`scripts/smoke_test.py N` falls back to a generic create/read/update/delete
check against a `records`-shaped resource once you replace your schema, that
check will start failing (`FAIL: GET /records returns 200`) unless your
feature's flow fits the same shape. Either add a `RESOURCES[N]` entry (see
student-1's `trips` entry) if it does, or write a dedicated
`student-N/tests/smoke_test.py` and a `check_student_N()` dispatcher in
`scripts/smoke_test.py` if it doesn't - student-2 and student-4 both do this,
for a places/favourites/recommendations flow and a sign-up/verification flow
respectively, neither of which is a single CRUD resource.

Branch, then open a pull request into `main`:

```bash
git checkout -b student-N/<feature>
git push -u origin student-N/<feature>
```
