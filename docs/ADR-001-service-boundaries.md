# ADR-001: Service boundaries, data ownership, and the AI request path

- Status: Accepted for Release 0
- Date: 2026-08-24
- Deciders: Group 25

## Context

Five students each build a frontend, a backend/API, and a database
microservice, and all fifteen services plus shared services must run as one
integrated application from a single Docker Compose configuration. Three
decisions had to be made before anyone could start on a feature, because
changing them later would touch every service.

## Decision 1: each database service exclusively owns its schema

Every `student-N-db` owns exactly one SQLite file and is the only process that
opens it. Any service needing another feature's data calls that feature's
database API over HTTP.

In each backend/API, all database calls live in a single module
(`services/database_api.py` in student-1). A service that reaches around it is
visible in review, which makes the rule enforceable rather than aspirational.

**Alternative rejected:** one shared SQLite file mounted into every container.
Simpler at first, but SQLite's write locking serialises writers across the whole
application, and it removes the service boundary the assessment is about.

## Decision 2: one shared AI-Mode service, not five Ollama clients

`ai-services/ai-mode` is the only service that talks to Ollama. Backends POST to
`/chat` and receive an answer. Model selection, prompt loading, and AI failure
handling live in one place.

Request flow: `Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM`.

This adds one internal hop over the specification's
`Frontend -> Backend/API -> Ollama -> LLM`. We accepted the hop because five
independent Ollama clients would mean five copies of the model configuration and
five different behaviours when the model is slow or absent, and because the
project specification also requires shared AI services to be containerised.

**Alternative rejected:** each backend calling Ollama directly. Fewer hops, but
the group would have no single place to change the model, and prompt artefacts
would be scattered across five directories.

## Decision 3: Ollama runs on the host by default

`docker-compose.yml` points AI-Mode at `host.docker.internal:11434`.

At least one team machine has 8 GB of RAM. Measured on that machine during Lab
02, `llama3.1:8b` needs a 6.2 GB working set and drops to roughly 0.05 tokens
per second under swap pressure. Running the runtime on the host lets each member
choose a model their machine can serve, and avoids a multi-gigabyte image in the
compose build.

The default serving model is `qwen2.5:0.5b`, which responds fast enough to
demonstrate live. `OLLAMA_MODEL` overrides it on a larger machine.

**Consequence:** the AI features need Ollama running before
`docker compose up`. `scripts/dev.sh up` warns when it is not. This must be part
of the deployment steps shown in the showcase video.

## Decision 4: one origin, via the shared frontend

`shared-frontend` reverse-proxies `/student-N/` to each student frontend and
`/api/student-N/` to each backend/API, so the browser only ever talks to
`localhost:8080`.

HTMX therefore makes same-origin requests, and the group avoids CORS
configuration in five separate services. Each student frontend still runs
standalone on its own port for individual development.

## Open question for the team

The shared access API and shared access database currently hold the
`travellers` table, while student-2 owns authentication, profile, and
onboarding. The boundary between "access" and "profile" needs to be agreed
before Release 1, or the two will duplicate user data.
