# NextStop - Group 25 Agentic AI Travel Application

41026 Advanced Software Development, Spring 2026 - Release 0.

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

Shared services: `shared-frontend` (8080), `shared-api` (5000), `shared-db`
(5200), `ai-mode` (5300).

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
- Ollama, with an approved model pulled: `ollama pull qwen2.5:0.5b`
- Python 3.11+ (only for the helper scripts; the services run in containers)

## Quick start

```bash
cp .env.example .env
./scripts/dev.sh up
open http://localhost:8080
```

`dev.sh up` builds every image, starts the integrated application, and waits
for the services to report healthy. The unified home page at
<http://localhost:8080> routes to all five student frontends and shows a live
health panel for every microservice.

Other commands:

```bash
./scripts/dev.sh health      # health of every service
./scripts/dev.sh smoke 1     # CRUD smoke test for student 1
./scripts/dev.sh loop        # the agentic loop, interactive
./scripts/dev.sh logs student-1-api
./scripts/dev.sh down        # stop and remove volumes
```

## Repository structure

```
.
├── .github/workflows/       student-1.yml .. student-5.yml
├── ai-services/
│   ├── ai-mode/             shared AI-Mode service (Flask, port 5300)
│   ├── agentic-loop/        Plan -> Act -> Observe -> Adapt loop (terminal)
│   └── prompts/             prompt engineering artefacts
│       ├── implementation/  prompts the running application uses
│       └── review/          prompts the agentic loop uses
├── docs/
│   ├── diagrams/            architecture diagrams (Mermaid)
│   ├── evidence/            screenshots and run records for the report
│   ├── ADR-001-service-boundaries.md
│   └── technical-report.md  the Release 0 report skeleton
├── scripts/                 dev.sh, smoke_test.py, wait_for_health.py, scaffold_student.py
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

## AI-Mode

`ai-mode` wraps Ollama's OpenAI-compatible API. Configure it in `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434/v1` | Ollama endpoint |
| `OLLAMA_MODEL` | `qwen2.5:0.5b` | model the application serves |
| `OLLAMA_REVIEW_MODEL` | `llama3.2:latest` | larger model for the agentic loop |

Ollama runs on the **host** by default, not in a container. On an 8 GB machine
`llama3.1:8b` needs a 6.2 GB working set and thrashes swap, so the default
serving model is the small `qwen2.5:0.5b`. Raise it on a machine with more RAM:

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
microservices architecture, and the DevOps pipeline.

```bash
./scripts/dev.sh loop            # interactive menu
./scripts/dev.sh loop all 2      # two iterations over all four targets
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

Students 2-5 currently have a generated scaffold: a working `records` CRUD
microservice trio, marked with `TODO` comments. The wiring already works, so
replace it from the bottom up:

1. `student-N/db/init_db.py` - your real schema, seeded with 10+ rows per table
2. `student-N/db/app.py` - CRUD endpoints for your resources
3. `student-N/api/app.py` - HTMX fragments for your feature
4. `student-N/frontend/templates/index.html` - your page, using the shared theme

`student-1/` shows the fuller layout (`routes/`, `services/`, `views/`) to move
to once a feature outgrows a single module.

Branch, then open a pull request into `main`:

```bash
git checkout -b student-N/<feature>
git push -u origin student-N/<feature>
```
