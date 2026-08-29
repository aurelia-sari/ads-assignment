# AI-assisted development: prompt engineering and context management

Evidence for **marking criterion 5** - *"Prompt engineering artefacts and AI
context management used during software development are documented"* - and for
project specification **section 4.4**, which requires each student to use
AI-assisted software engineering, and **section 4.6**, which requires that all
AI-generated work be validated before submission.

Student: Caroline Zhou (student-1)
Tool: Claude (specification section 4.5, optional tool list)
Local product LLMs: Qwen 2.5 and Llama 3.2 via Ollama (sections 4.1-4.2)

There are two distinct uses of AI in this project and they are documented
separately:

| | What | Where documented |
|---|------|------------------|
| AI **in** the product | AI-Mode, the chatbot, the agentic loop | `ai-services/prompts/`, report appendix A |
| AI **for** development | Claude, used to build the microservices | **this document** |

---

## 1. Context management

A general-purpose model knows nothing about this assignment. Most of the work
of using one well was deciding what it should be told, and making that context
durable rather than re-explaining it every session.

### 1.1 Sources of truth, in priority order

| Source | Supplies |
|--------|----------|
| `ASD_2026_Project_Specifications.pdf` | Requirements, repository structure, submission list. Read directly rather than summarised, so requirements were quoted not paraphrased. |
| Canvas assignment page and rubric | The ten marking criteria and their weights |
| `asd-labs/enrolment-app-open-ai` | The conventions taught in labs: Flask + HTMX, `routes/`/`services/`/`views/` split, Ollama through the OpenAI-compatible client |
| `docs/ADR-001-service-boundaries.md` | Decisions already made, so they were not silently re-litigated |
| `docs/CONTRIBUTING.md` | Team rules that constrain any change |

### 1.2 Practices that mattered

**Ground in the real artefact, not a description of it.** The lab reference app
was read before any code was written, so the generated services match the
conventions taught in the subject rather than generic Flask idiom. The
specification was read as a PDF rather than summarised, so the repository
structure follows section 7.1 exactly.

**Write decisions down where they will be re-read.** ADR-001 exists so that a
later session does not re-open a settled question. It is context management for
the team and for the model at once.

**Keep the assumption visible.** Where something was assumed rather than
verified - the student-to-slot mapping - it was recorded as an assumption in
the README with an instruction to check it. It was later found to be wrong for
four of five students, and the note is what made that cheap to fix.

**Prefer verification over assertion.** The most useful pattern was not a
prompt at all: after each change, run the thing and check the output. Section
3 lists what that caught.

---

## 2. How AI assistance was used, by activity

Mapped to the activities listed in specification section 4.4.

| Activity | How it was used | Validation applied |
|----------|-----------------|--------------------|
| Requirements analysis | Extracting the submission checklist and the ten criteria from the specification PDF | Cross-checked against the Canvas rubric |
| Software design | Service boundaries, data ownership, the AI request path | Written up as ADR-001 with alternatives and their costs |
| Code generation | The microservices, the agentic loop, the CI workflows | Every service built and run; CRUD exercised end to end |
| Software testing | `smoke_test.py`, `wait_for_health.py` | Asserted against a known-broken revision to prove the tests fail when they should |
| Debugging | The nginx deadlock, the httpx incompatibility, the CI race | Each reproduced first, then fixed, then re-verified |
| Refactoring | Extracting `services/shared_api.py` for cross-feature reads | Smoke test extended to cover it |
| Technical documentation | This report, the README, the ADR | Checked against the specification's required section list |

---

## 3. Where AI-generated work was wrong, and how it was caught

This is the substance of specification section 4.6. Generated code was wrong
often enough that validation was not a formality. Recording the failures is
more honest evidence of validation than recording only successes.

| # | AI-generated defect | How it was caught | Fix |
|---|---------------------|-------------------|-----|
| 1 | `resolver 127.0.0.11` written into every nginx config to defer DNS - but the directive is inert unless `proxy_pass` targets a **variable**, so it did nothing | A rebuild put the hub and a student frontend into a mutual crash loop | All upstreams changed to variables with explicit `rewrite` |
| 2 | `openai==1.51.0` pinned without pinning `httpx`; 1.51 passes `proxies=` to `httpx.Client`, removed in httpx 0.28 | `ai-mode` crash-looped on first `docker compose up` | Pinned `httpx==0.27.2` |
| 3 | Agentic loop collector counted `docker build` and missed `docker compose build`, reporting "0 build steps" | Read the loop's own output instead of trusting it | Counted both spellings |
| 4 | Same collector line-parsed YAML and reported 28 services, counting comments, volumes and networks | Compared against `docker compose config` | Parsed with PyYAML |
| 5 | f-string with nested same-type quotes - invalid before Python 3.12, and the containers run 3.11 | `ast.parse` check before building | Extracted to a variable |
| 6 | Health probes were sequential with a 2s timeout, reporting healthy services as down whenever the host was busy | Panel showed `shared-db` down while its container was up | Concurrent probes, 6s timeout |
| 7 | Smoke tests validated the API and database but never that the page called them | A teammate's design change removed every HTMX attribute and CI stayed green | Frontend wiring assertions added, verified against the broken revision |
| 8 | Student-to-slot mapping assumed rather than confirmed | Checked against the team's actual allocation | Corrected before anyone built on it |

Defects 1, 6 and 7 share a shape worth naming: the generated code was
*plausible* and passed every check that existed, because the check tested a
layer below the one that mattered. Plausibility is the specific failure mode of
a language model, and it is why "it runs" is not validation.

---

## 4. Prompting patterns that worked

**Ask for the failure case, not the happy path.** "What happens if shared-api
is down?" produced the degradation behaviour in `services/shared_api.py`. Asking
only for the feature produced code that assumed every dependency was up.

**Require the model to cite evidence.** In the agentic loop's review prompts,
adding *"refer only to files that appear verbatim in the evidence"* eliminated a
class of hallucination where the model invented `schemaRepository.js` and Java
files. See report appendix A.1 for the before and after.

**Constrain the vocabulary.** Telling the model the actual stack - Flask, nginx,
HTMX, SQLite - stopped it reaching for idioms from other ecosystems.

**Reject the first answer when it is only plausible.** Defects 3 and 4 above
were both accepted at first glance and only caught by reading the output
against reality.

---

## 5. Artefacts

| Artefact | Location |
|----------|----------|
| Product prompts, implementation | `ai-services/prompts/implementation/` |
| Product prompts, agentic review | `ai-services/prompts/review/` |
| Prompt iteration with before/after | Report appendix A |
| Agentic loop run records | `ai-services/agentic-loop/runs/`, sample in `docs/evidence/` |
| Development-time context and validation | this document |
| Commit-level attribution | `Co-Authored-By` trailers, visible in `git log` |
