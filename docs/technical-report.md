# Release 0 Technical Report - Group 25

**41026 Advanced Software Development, Spring 2026**
**Project: Wander - Agentic AI travel planning application**

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

Wander is an Agentic AI travel planning application. A traveller plans trips,
builds a day-by-day itinerary, discovers attractions and dining, tracks
bookings and budget, and finds a travel companion. Local LLM support runs
through a shared AI-Mode service.

*To write: the real-world problem, target user, and scope of Release 0.*

### 1.1 Team members and individual feature allocation

| Slot | Student | Feature | Frontend | Backend/API | Database |
|------|---------|---------|----------|-------------|----------|
| student-1 | Caroline Zhou | Trips & Itinerary (day-by-day) + AI chatbot | :8081 | :5101 | :5201 `trips`, `itinerary_days` |
| student-2 | Aurelia Sari | Auth, profile, onboarding, dashboard, travel guides | :8082 | :5102 | :5202 |
| student-3 | Kevin Kim | Sightseeing, attractions, restaurants, recommendations | :8083 | :5103 | :5203 |
| student-4 | Aung Ko Khaing | Flights, hotels, car rentals, budget | :8084 | :5104 | :5204 |
| student-5 | Tanishpreet Kour | Travel mate matching | :8085 | :5105 | :5205 |

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
| F1.5 | Add, view and delete day-by-day itinerary entries for a trip | Days display in day-number order |
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

*One per student: scope, tasks, order of work, and what is deferred to Release 1.*

### 2.6 Risk management plan **(Individual)**

*One per student. Group-level risks that are already known:*

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| A team machine cannot serve a large LLM (8 GB RAM measured at 0.05 tok/s on `llama3.1:8b`) | High | Medium | Default to `qwen2.5:0.5b`; `OLLAMA_MODEL` is per-machine |
| Ollama not running before the demo, so every AI feature fails live | Medium | High | `scripts/dev.sh up` warns; deployment steps in the video start Ollama first |
| Integration slips to the last week and features do not connect | Medium | High | The scaffold integrates all five slots from day one; CI runs on every PR |
| Merge conflicts in `docker-compose.yml` | Medium | Low | Each student edits only their own block |
| A student's feature works standalone but is not integrated (scores 0) | Low | High | Smoke test runs against the shared compose file, not a local copy |

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

*Screenshots of green runs for all five workflows into `docs/evidence/`.*

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
| 5 | The shared access API and student-2's auth feature overlap | Risk of duplicate user data | Agree the boundary before Release 1 |
| 6 | No automated tests beyond the smoke test | Limited regression cover | pytest is a Release 2 requirement |

---

## 10. Project evidence

### 10.1 GitHub commit logs

```bash
git log --pretty=format:'%h %an %ad %s' --date=short
```

### 10.2 Contribution logs **(Individual)**

| Student | Contribution | Commits | Evidence |
|---------|--------------|---------|----------|
| | | | |

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
