# Release 0 Technical Report - Group 25

**41026 Advanced Software Development, Spring 2026**
**Project: NextStop - Agentic AI travel planning application**

> Working draft. Export to PDF for submission - Canvas accepts one group PDF.
>
> **Deadline conflict to resolve with the tutor:** the project specification and
> the assignment page both say 30 August 2026, 11:59 PM AEST. The Canvas due
> date field says 6 September 2026, 11:59 PM. Assume 30 August until confirmed.
>
> Every section below is required by section 10.3 of the project
> specification. Sections marked **(Individual)** need one subsection per
> student; a missing individual subsection costs that student marks, not the
> group.

---

## 1. Project overview

NextStop is an Agentic AI travel planning application. A traveller plans trips,
builds a day-by-day itinerary, discovers attractions and dining, tracks
bookings and budget, and finds a travel companion. Local LLM support runs
through a shared AI-Mode service.

*To write: the real-world problem, target user, and scope of Release 0.*

### 1.1 Team members and individual feature allocation

| Slot | Student | Feature | Frontend | Backend/API | Database |
|------|---------|---------|----------|-------------|----------|
| student-1 | Caroline Zhou | Trips & Itinerary (day-by-day) + AI chatbot | :8081 | :5101 | :5201 `trips`, `itinerary_days` |
| student-2 | Kevin Kim | Sightseeing, attractions, restaurants, recommendations | :8082 | :5102 | :5202 |
| student-3 | Tanishpreet Kour | Travel mate matching | :8083 | :5103 | :5203 |
| student-4 | Aurelia Sari | Auth, profile, onboarding, dashboard, travel guides | :8084 | :5104 | :5204 |
| student-5 | Aung Ko Khaing | Flights, hotels, car rentals, budget | :8085 | :5105 | :5205 |

For each feature the specification (section 2.4) requires a feature name, a
brief description, and a description of the frontend, backend/API, and database
microservices. *Each student writes their own row's detail.*

---

## 2. Project analysis and planning

### 2.1 Agile team project plan (Group)

*To write: sprint length, ceremonies, how work was allocated and tracked.*

### 2.2 Sprint backlog (Group)

| ID | Item | Owner | Type | Sprint | Status |
|----|------|-------|------|--------|--------|
| | | | | | |

### 2.3 Overall project plan (Group)

*To write: Release 0, 1 and 2 milestones against the semester schedule.*

### 2.4 Functional and non-functional requirements **(Individual)**

Each student adds their own requirements to the sprint backlog and lists them
here.

#### student-1 - Caroline Zhou

Functional:

| ID | Requirement | Acceptance criteria |
|----|-------------|---------------------|
| F1.1 | Create a trip with name, destination, dates, traveller, budget and status | Trip appears in the trip table with a generated ID |
| F1.2 | Read trips, filtered by destination or status | Filtered table returns only matching trips |
| F1.3 | Update any field of an existing trip | Changed values persist and redisplay |
| F1.4 | Delete a trip and its itinerary days | Trip and its days are both removed |
| F1.5 | Add, view, update and delete day-by-day itinerary entries for a trip | Days display in day-number order; edits persist and redisplay |
| F1.6 | Ask the AI chatbot a question grounded in real trip data | Answer references the traveller's actual trips |

Non-functional:

| ID | Requirement | How it is met |
|----|-------------|---------------|
| N1.1 | The backend never opens the SQLite file directly | All database access goes through `services/database_api.py` |
| N1.2 | A database or AI outage does not show a stack trace to the user | Routes catch `RequestException` and return a notice fragment |
| N1.3 | User-supplied text cannot inject HTML | All values pass through `html.escape` in `views/formatters.py` |
| N1.4 | The page matches the team UI | The page links `/shared/css/theme.css` only |

*students 2-5: add your subsections here.*

### 2.5 Feature plan **(Individual)**

#### student-1 - Caroline Zhou - Trips & Itinerary

**Scope.** A traveller creates a trip, builds a day-by-day itinerary against it,
and asks an AI chatbot questions grounded in that data. Two tables, both with
full CRUD, plus one AI surface.

**Why this order.** The work was sequenced bottom-up, so that every layer was
verifiable before anything depended on it. A frontend built against an unproven
API produces two suspects when something breaks.

| # | Task | Deliverable | Done |
|---|------|-------------|------|
| 1 | Database schema and seed | `trips` (12 rows), `itinerary_days` (15 rows) | 24 Aug |
| 2 | Database API | CRUD over HTTP on both tables, port 5201 | 24 Aug |
| 3 | Backend/API | HTMX fragments, `routes/` `services/` `views/` split | 24 Aug |
| 4 | Frontend | Three tabs, shared CSS theme | 24 Aug |
| 5 | AI-Mode integration | Chatbot grounded in live trip data | 24 Aug |
| 6 | CI workflow | `student-1.yml`, build + health + CRUD validation | 24 Aug |
| 7 | Cross-feature read | Resolve `traveller_id` via the shared access API | 24 Aug |
| 8 | Complete itinerary CRUD | Update on days, closing a gap found in review | 28 Aug |

**Design decisions worth defending.**

1. *One module owns database access.* Every call to `student-1-db` goes through
   `services/database_api.py`. The data-ownership rule is then checkable by
   reading one file rather than auditing every route.
2. *The backend returns HTML, not JSON.* HTMX swaps fragments directly, so
   there is no client-side rendering layer to keep in sync with the API.
3. *Cross-feature data is fetched, never copied.* A trip stores `traveller_id`
   and nothing else about the traveller. The name is resolved at render time
   from the shared access API, so there is one source of truth.
4. *Every external call degrades.* If the shared API is down the table shows
   `#7` instead of a name; if AI-Mode is down the chatbot returns a notice, not
   a stack trace. One service failing must not take the feature down.

**Deferred to Release 1.**

- Ground the chatbot in retrieved context via the RAG server, rather than the
  hand-built summary in `routes/ai_chat.py`
- Expose trips through the MCP server so other features can query them
- Reconcile itinerary days against Kevin's attractions, so a day can reference a
  real place rather than free text
- Server-side pagination once the trip count outgrows a single table

### 2.6 Risk management plan **(Individual)**

#### student-1 - Caroline Zhou

Risks are rated for their effect on **my** deliverable. Several already
occurred during Release 0, so this register records what actually happened and
what was put in place afterwards, rather than only what might.

**Risks that materialised**

| # | Risk | Impact | What happened | Response |
|---|------|--------|---------------|----------|
| R1 | A teammate's change breaks my feature | **High** | A design commit replaced my page with static markup. Every `hx-*` attribute and API call was removed. The feature looked fine and did nothing. | `smoke_test.py` now asserts each page carries HTMX attributes and calls its own API. Team convention agreed: a design change must preserve `hx-*` wiring. |
| R2 | Green CI while the feature is broken | **High** | The tests validated the API and database, never that the page called them. R1 passed CI. | Frontend wiring assertions added. Verified against the broken revision - it now fails. |
| R3 | A race-dependent bug survives testing | **High** | nginx resolved upstreams at startup, so the hub required all five frontends to exist. It passed repeatedly, then deadlocked when start order shifted. | All `proxy_pass` targets are variables, resolved per request. A missing service now 502s on its own route only. |
| R4 | Shared files edited in parallel | Medium | `theme.css` was replaced rather than extended, dropping 24 classes four other pages relied on. | Component layer restored on top of the new design. Convention agreed: extend the theme, never replace it. |
| R5 | Dependency version drift | Medium | `openai==1.51` passed `proxies=` to `httpx`, which 0.28 removed. AI-Mode crash-looped. | `httpx` pinned to 0.27.2. |
| R6 | Work built on a wrong assumption | Medium | The student-to-slot mapping was assumed rather than confirmed, and was wrong for four of five. | Corrected before anyone built on it. Ownership is now in the README, in file headers, and on each page. |

**Open risks**

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|------|-----------|--------|------------|-------|
| R7 | Ollama not running at showcase, so every AI feature fails live | Medium | **High** | `dev.sh up` warns when port 11434 is unreachable. Starting Ollama is an explicit step in the demo script and is shown in the video. | Me |
| R8 | The demo machine cannot serve the model | Medium | **High** | Default is `qwen2.5:0.5b`, which runs on the 8 GB machine. `OLLAMA_MODEL` is per-machine, so no one is forced onto a model their laptop cannot run. | Me |
| R9 | The home page loads 8 images from `picsum.photos`; venue wifi fails | Medium | Medium | Copy the images into `shared/assets/` and serve them locally before the showcase. **Not yet done.** | Team |
| R10 | Cross-feature reference integrity | Low | Low | SQLite cannot enforce a reference across a service boundary, so a trip can point at a deleted traveller. Display degrades to `#<id>`. Accepted for Release 0; see ADR-001. | Me |
| R11 | Report evidence cannot be reconstructed after the fact | Medium | **High** | Screenshots, CI logs and loop run records are collected into `docs/evidence/` as work happens, not at the end. | Team |
| R12 | Integration slips because features are built in isolation | Low | **High** | The scaffold integrated all five slots from day one, and CI runs against the shared compose file rather than a local copy. | Team |

**What I would carry into Release 1.** R1, R2 and R3 share a shape: something
passed every check and was still broken, because the check tested a layer below
the one that mattered. The response in each case was to move the assertion up to
the layer a marker or user actually touches. Release 1 adds MCP and RAG, where
the same trap exists - a retrieval call can succeed and still return nothing
useful - so the tests need to assert on grounded output, not just on a 200.

### 2.7 Data design

Conceptual, ERD, logical and physical models. *Each student covers their own
tables.* student-1's physical model:

```sql
CREATE TABLE trips (
    trip_id      INTEGER PRIMARY KEY,
    trip_name    TEXT NOT NULL,
    destination  TEXT NOT NULL,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    traveller_id INTEGER NOT NULL,
    budget_aud   REAL NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'planned'
);

CREATE TABLE itinerary_days (
    day_id     INTEGER PRIMARY KEY,
    trip_id    INTEGER NOT NULL,
    day_number INTEGER NOT NULL,
    day_date   TEXT NOT NULL,
    location   TEXT NOT NULL,
    activity   TEXT NOT NULL,
    notes      TEXT DEFAULT '',
    FOREIGN KEY (trip_id) REFERENCES trips (trip_id) ON DELETE CASCADE
);
```

Seeded with 12 trips and 15 itinerary days, above the ten-record minimum.

`traveller_id` is a **cross-feature reference, not a foreign key**. Traveller
records live in the shared access database, which is a different service, so
SQLite cannot enforce the relationship. student-1 resolves it over HTTP through
`services/shared_api.py` and renders the traveller's name in the trip table.

This is the application's data-ownership model in miniature, and ADR-001
records why it was chosen over one shared database: SQLite takes a
database-level write lock, so a single file behind fifteen writer containers
would serialise every write and risk corruption. The accepted cost is that
referential integrity across features is advisory - a trip can reference a
traveller that no longer exists, and the table falls back to `#<id>`.

| Owner | Holds | Examples |
|-------|-------|----------|
| `shared-db.travellers` | Identity - what every feature needs to answer "who" | traveller_id, name, email, home city |
| `student-4` database | Profile - what only the account feature needs | preferences, onboarding state, dashboard layout |

`traveller_id` is the join key across all five features and is the only
traveller field another feature may store.

---

## 3. Repository structure

*Paste the tree from README.md and explain the separation between shared
components and individual student components.*

---

## 4. Software architecture

### 4.1 Individual software architecture **(Individual)**

One diagram per student. student-1: `docs/diagrams/student-1-architecture.mmd`.

### 4.2 Integrated Release 0 software architecture

`docs/diagrams/integrated-architecture.mmd`.

Key decisions are recorded in `docs/ADR-001-service-boundaries.md`:

1. Each database service exclusively owns its schema; cross-feature data moves
   over HTTP only.
2. One shared AI-Mode service instead of five Ollama clients.
3. Ollama runs on the host by default, for RAM reasons.
4. One origin: `shared-frontend` reverse-proxies every student frontend and API.

### 4.3 Docker Compose architecture

`docs/diagrams/docker-compose-architecture.mmd`. Nineteen containers: three
shared, fifteen student, one shared AI service, plus the terminal-only
`agentic-loop` under the `tools` profile.

### 4.4 DevOps pipeline architecture

`docs/diagrams/devops-pipeline.mmd`.

---

## 5. Agentic AI

### 5.1 Plan -> Act -> Observe -> Adapt workflow

`docs/diagrams/agentic-loop.mmd`. The ACT step collects real evidence - live
HTTP calls and reads of the compose and workflow files - so OBSERVE reviews
facts rather than assumptions, and ADAPT's "next check" seeds the following
iteration.

### 5.2 AI-Mode implementation

| Item | Implementation |
|------|----------------|
| AI-Mode | `ai-services/ai-mode`, Flask on :5300 |
| Ollama runtime | Host, `host.docker.internal:11434/v1` |
| Approved LLM | `qwen2.5:0.5b` serving, `llama3.2:latest` for review |
| Request flow | Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM |

### 5.3 Prompt engineering and context management

Prompt artefacts live in `ai-services/prompts/`, split into `implementation/`
(prompts the running application uses) and `review/` (prompts the agentic loop
uses).

| Prompt | Role |
|--------|------|
| `implementation/system_prompt.txt` | Chatbot persona and grounding rules |
| `implementation/chatbot_task_prompt.txt` | What the chatbot should do with a question |
| `implementation/chatbot_context_prompt.txt` | Schema and units the model can rely on |
| `review/planner_system_prompt.txt` | Reviewer persona for the agentic loop |
| `review/plan_prompt.txt` | PLAN step |
| `review/observe_prompt.txt` | OBSERVE step |
| `review/adapt_prompt.txt` | ADAPT step |
| `review/*_review_prompt.txt` | One per review target |

Context management: `routes/ai_chat.py` builds a plain-text summary of the
traveller's live trips and itinerary days and passes it as context, so the model
answers about trips that exist. When the database is unreachable the chatbot
answers without grounding rather than failing outright.

*To write: prompt iterations - what was tried, what failed, what changed.
This criterion is worth 2 marks and is documentation only.*

### 5.4 Agentic loop workflow record

*Paste a run from `ai-services/agentic-loop/runs/` here, or reference the copy
in `docs/evidence/`. Each student identifies the prompts they contributed.*

---

## 6. DevOps and CI/CD

### 6.1 GitHub Actions workflow files

`student-1.yml` to `student-5.yml`. Each one:

1. checks out the shared repository
2. byte-compiles that student's source
3. validates the shared compose configuration
4. builds the student's three microservices
5. starts them with the shared compose file
6. waits for `/health` on the database, API, and AI-Mode
7. runs `scripts/smoke_test.py N` - full CRUD plus a fragment check
8. curls the frontend
9. dumps container logs on failure and always tears down

Triggers: pushes to `main` and pull requests touching that student's directory,
the shared directories, or `docker-compose.yml`.

### 6.2 GitHub Actions execution evidence

All five workflows passed on pull request #1 and again on `main` after the
merge - ten green runs, 57s to 1m8s each, on clean GitHub-hosted runners.

Full logs: **`docs/evidence/github-actions-execution.md`**, which for each
workflow records the run URL, trigger, commit, the three images built, the
compose start-up, the health wait, and the complete CRUD validation output.

| Workflow | Feature | Owner | Result |
|----------|---------|-------|--------|
| `student-1.yml` | Trips & Itinerary | Caroline Zhou | success |
| `student-2.yml` | Attractions & Dining | Kevin Kim | success |
| `student-3.yml` | Travel Mate | Tanishpreet Kour | success |
| `student-4.yml` | Account & Dashboard | Aurelia Sari | success |
| `student-5.yml` | Bookings & Budget | Aung Ko Khaing | success |

One detail worth drawing out for the architecture section: each workflow starts
only `shared-frontend` and that student's three services, yet the compose
start-up log shows `shared-db` and `shared-api` coming up as well. Docker
Compose resolved the `depends_on` chain, which is what allows the cross-feature
traveller lookup to be exercised in CI rather than only on a developer machine.

*Still to add: screenshots of the Actions tab and the PR checks view.*

### 6.3 Docker Compose execution evidence

*`docker compose up --build` output and `docker compose ps` showing all
containers up, into `docs/evidence/`.*

---

## 7. Implementation summary

*What was built in Release 0, per student.*

---

## 8. Testing evidence

### 8.1 Local testing evidence

```
$ python3 scripts/smoke_test.py 1
Smoke test: student-1
  ok  database service is healthy
  ok  backend/API service is healthy
  ok  GET /trips returns 200
  ok  /trips is seeded with at least 10 records (found 12)
  ok  POST /trips creates a record (201)
  ok  PUT /trips/13 updates it
  ok  DELETE /trips/13 removes it
  ok  GET /trips/13 is 404 after delete
  ok  backend/API returns an HTML fragment, not JSON

student-1 passed all checks.
```

*Add the runs for students 2-5.*

### 8.2 Screenshots of the integrated application

*Into `docs/evidence/`: the unified home page with the health panel, each
student's feature, and the AI chatbot answering.*

---

## 9. Known issues and limitations

| # | Issue | Impact | Plan |
|---|-------|--------|------|
| 1 | Students 2-5 still hold the generated `records` scaffold rather than real feature schemas | Those features are not yet real | Each owner replaces their schema, routes and page |
| 2 | Ollama runs on the host, not in a container | Deployment has a manual prerequisite | Document in the video; containerise if RAM allows |
| 3 | `qwen2.5:0.5b` is small and its answers are shallow | Demo quality | Raise `OLLAMA_MODEL` on a larger machine |
| 4 | AI-Mode adds one hop over the specification's direct Backend -> Ollama flow | Deviation from the spec diagram | Justified in ADR-001 |
| 5 | Cross-feature referential integrity is advisory - SQLite cannot enforce a reference across service boundaries | A trip can point at a deleted traveller | Display degrades to `#<id>`; a reconciliation check is a Release 1 candidate |
| 6 | No automated tests beyond the smoke test | Limited regression cover | pytest is a Release 2 requirement |
| 7 | The agentic loop's ACT evidence is accurate, but `llama3.2:latest` (3B) still miscounts it and occasionally names files that do not exist | Review findings need a human check before being acted on | Tightened grounding prompts (Appendix A.1) removed the worst of it; a larger review model on a 16 GB machine is the real fix |

---

## 10. Project evidence

### 10.1 GitHub commit logs

```bash
git log --pretty=format:'%h %an %ad %s' --date=short
```

### 10.2 Contribution logs **(Individual)**

| Student | Contribution | Commits | Evidence |
|---------|--------------|---------|----------|
| Caroline Zhou | Repository scaffold and shared architecture; Trips & Itinerary feature (2 tables, full CRUD, AI chatbot); shared AI-Mode service; agentic loop; all five CI workflows; cross-feature read; ADR-001 | 8 | `git log --author=caramelchew` |
| Kevin Kim | Attractions & Dining feature: 3 tables (`places` 15, `favourites` 10, `recommendations` 10), CRUD, AI integration | 6 | PR #6 |
| Aung Ko Khaing | Landing page design and shared CSS theme (navy/cream palette, Poppins + Inter) | 1 | commit `b2678a0` |
| Tanishpreet Kour | *(to complete)* | | |
| Aurelia Sari | *(to complete)* | | |

Per-student commit counts:

```bash
git shortlog -sn --all
```

#### Caroline Zhou - detail

| Date | Contribution |
|------|--------------|
| 24 Aug | Repository scaffold: 18-container Compose stack, shared frontend/API/DB, AI-Mode service, agentic loop, 5 CI workflows, docs |
| 24 Aug | Trips & Itinerary: schema + seed, database API, backend/API, HTMX frontend, AI chatbot |
| 24 Aug | Cross-feature traveller resolution with caching and graceful degradation; corrected the student slot mapping |
| 24 Aug | Fixed an nginx startup deadlock and a CI readiness race |
| 28 Aug | Restored feature-page function after a design regression; added frontend wiring assertions to CI |
| 28 Aug | Completed CRUD on itinerary days |

### 10.3 Attendance checkpoints

| Week | Date | Attended | Notes |
|------|------|----------|-------|
| | | | |

---

## 11. Showcase video

**Video URL:** *(paste the published URL here - required, 10 minutes max)*

The video must show:

- the integrated application running
- every student demonstrating their own feature
- deployment steps, including starting Ollama
- the agentic loop executing in the terminal
- the CI/CD pipeline

All five students must appear. All five must attend the Week 6 showcase -
non-attendance scores 0.

---

## Appendix A: prompt engineering iterations

Evidence for marking criterion 5 (prompt engineering and context management).

### A.1 Grounding the agentic loop's reviewer

**Problem observed.** The first version of `review/planner_system_prompt.txt`
described the reviewer's role but said nothing about what the project is made
of. Running the loop against the DevOps target with `llama3.2:latest`, the
model's ADAPT step proposed creating `schemaRepository.js`, adding settings to
`config.json`, and checking
`src/main/java/com/example/student/frontend/StudentFrontend.java` - none of
which exist. The ACT step's evidence was correct; the model invented a
JavaScript and Java codebase around it.

**Change.** Three additions to the prompts:

1. The system prompt now states the actual stack (Flask, nginx, HTMX, SQLite,
   GitHub Actions, Docker Compose) and adds explicit grounding rules, including
   "there are no .js, .json, or .java files in this project".
2. The OBSERVE prompt now forces a planned check that the evidence is silent
   about into ISSUE as "not shown by the evidence", rather than letting the
   model credit it as a PASS.
3. The ADAPT prompt now requires the proposed change to address something the
   observations actually flagged, and to say so when every check passed instead
   of inventing a defect.

**Why it matters.** The value of this loop is that ACT collects real evidence.
A model that invents filenames discards that advantage. Constraining the output
vocabulary to what appears in the evidence is what makes the review usable.

**Result.** The invented JavaScript and Java vocabulary disappeared, and the
model stayed within the project's real file names. It still miscounted the
services in `docker-compose.yml` and referred once to a `main.yml`. Prompt
grounding fixed the vocabulary problem but not the counting problem, which is
a capability limit of a 3B model rather than a prompt defect.

A sample run is committed at `docs/evidence/agentic-loop-sample-run.md`.

*To do: attach the before/after ADAPT output side by side for the report.*

### A.2 Grounding the traveller chatbot

`routes/ai_chat.py` builds a plain-text summary of the traveller's real trips
and itinerary days and passes it as context, so answers reference trips that
exist. `implementation/system_prompt.txt` adds two rules that matter for a
travel assistant: say so plainly when the data does not contain the answer, and
never claim to have made or changed a booking.

*To do: record an example answer with and without the grounding context.*

### A.3 Model selection

`qwen2.5:0.5b` serves the application because it responds fast enough to
demonstrate live. `llama3.2:latest` runs the review loop, where a slower and
more capable model is worth the wait. Both are configurable per machine through
`.env`, because team hardware differs - see ADR-001, decision 3.

*To do: note any further model changes and the reason for each.*
