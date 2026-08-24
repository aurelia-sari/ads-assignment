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

## Decision 5: identity is shared, profile is a feature

The shared access database holds `travellers` while student-4 owns
authentication, profile, and onboarding. Without a rule these two duplicate
user data, so the boundary is:

| Owner | Holds | Examples |
|-------|-------|----------|
| `shared-db.travellers` | **Identity** - the minimum every feature needs to answer "who is this" | traveller_id, full name, email, home city, member since |
| `student-4` database | **Profile** - everything about a traveller that is a feature, keyed by traveller_id | preferences, onboarding state, dashboard layout, saved guides, avatar |

The test for which side something belongs on: if more than one feature needs it
to render a row, it is identity. If only the account feature needs it, it is
profile.

`traveller_id` is the join key across the whole application, and it is the only
traveller field any other feature is allowed to store.

**Consequence:** student-4 must not add a `full_name` column. When the account
feature needs a name it reads it from the shared access API, the same way
student-1 does.

## How cross-feature reads actually work

student-1 is the worked example the other four features should copy.

A trip stores `traveller_id`, but student-1 does not own traveller records. So
`student-1/api/services/shared_api.py` fetches them over HTTP from the shared
access API and the trip table renders the name:

```
student-1-api  --HTTP-->  shared-api  --HTTP-->  shared-db  (travellers)
```

Three properties that make this safe, and that any cross-feature read should
copy:

1. **One call, not N.** The traveller list is fetched once per render and
   indexed by id, rather than one request per row.
2. **A short TTL cache.** 30 seconds, because the table re-renders on every
   filter change. Stale names for half a minute are harmless; cache
   invalidation across services is not worth the complexity here.
3. **Degrade, do not fail.** If the shared service is unreachable, the trip
   table still renders and shows `#<id>` instead of a name, and the trip form
   falls back from a picker to a number input. One feature being down must not
   take another feature down with it.

Point 3 is the one that matters most on demo day: a service that is slow to
start cannot break someone else's demonstration.

`scripts/smoke_test.py 1` asserts the resolved name appears and that no row
fell back to a raw id, so a broken cross-feature read fails CI rather than
quietly degrading.

## Rejected: one shared database for the whole application

Worth recording, because it is the obvious first instinct and the reasons
against it are specific to this project.

Five features in one domain do have genuinely related data - trips reference
travellers, bookings will reference trips - and a single database would allow
real foreign keys and joins instead of HTTP round trips. On a different stack
that would be a serious contender: one PostgreSQL instance with a schema per
feature gives most of the isolation while keeping referential integrity, and we
would likely choose it.

It is the wrong call here for two reasons:

1. **SQLite does not share.** SQLite takes a database-level write lock. One
   file behind fifteen writer containers means `SQLITE_BUSY` under any real
   concurrency, and a meaningful corruption risk on a shared Docker mount.
   The specification mandates SQLite for Release 0, so a single shared file is
   not a workable design regardless of what we would prefer.
2. **It removes the boundary being assessed.** The project specification
   requires that each database container own its schema and that other services
   reach it only through its API. A shared database makes that rule
   unenforceable by construction.

The cost we accept: no cross-feature foreign keys, and no transaction spanning
two features. Referential integrity across features is therefore advisory -
`trips.traveller_id` can point at a traveller that no longer exists, and the
display falls back to `#<id>` when it does. For a trip planner that is an
acceptable trade. An application that needed atomic cross-feature writes would
need a different data architecture, and that is worth saying out loud rather
than discovering it in Release 2.
