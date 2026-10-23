# Release 2 Technical Report - Group 25

**41026 Advanced Software Development, Spring 2026**
**Project NextStop - Agentic AI travel planning application**

---

## Pre-Commit Security Testing

Set up by Aurelia Sari for the whole team.

Every commit runs three local scans from `.pre-commit-config.yaml`. Each hook
calls `security/run_scan.py`, which runs one pytest file per scan, so a failure
shows the tool output as a readable assertion message. Any finding blocks the
commit.

| Hook | Tool | Runs |
|------|------|------|
| `ruff-security` | Ruff `S` rules (flake8-bandit), S101 ignored in tests | every commit, whole repository |
| `detect-secrets` | detect-secrets against `.secrets.baseline` | every commit, all tracked files |
| `pip-audit` | pip-audit on every `requirements*.txt` | only when a requirements file is staged |

pip-audit queries an online vulnerability database, so it is slow and fails
offline. Its hook sets `files` to match `requirements*.txt`, and pre-commit
skips a hook when no staged file matches. The other two hooks set
`always_run`.

The first full scan flagged every student folder. PR 59 upgraded the
vulnerable pins and marked each reviewed false positive with a one line
`noqa` and its reason. Findings in `shared/`, `ai-services/` and `scripts/`
were handled the same way. Every unit test, smoke test and frontend check gave
the same result before and after. The full scan output is in
`docs/evidence/pre-commit-security-scan.txt`.

### Findings by folder

Paths are inside the folder named in the first column. Not fixed means the
finding was reviewed as a false positive, so PR 59 kept the code and marked the
line with `noqa` or recorded it in the secrets baseline, for the owner to
confirm. For fixed rows the reason says why the change was needed. A `noqa`
silences only that one rule on that one line, so any new finding is still
caught.

| Folder | Scan and rule | Meaning | Where | Status | Reason |
|---|---|---|---|---|---|
| student-1 | Ruff S104 | binds to all interfaces | `api/app.py` 47 | Not fixed, `noqa` | other containers must reach the service |
| student-1 | Ruff S608 | SQL built from a string | `db/app.py` 115, 146, 223, 254 | Not fixed, `noqa` | column names come from a fixed list and values are bound |
| student-1 | pip-audit | vulnerable Flask, flask-cors, requests, pytest | `api`, `db`, `tests` requirements | Fixed, pins upgraded | known vulnerabilities |
| student-2 | Ruff S104 | binds to all interfaces | `api/app.py` 72, `db/app.py` 542 | Not fixed, `noqa` | other containers must reach the service |
| student-2 | Ruff S608 | SQL built from a string | `db/app.py` 271, 308 | Not fixed, `noqa` | column names come from a fixed list and values are bound |
| student-2 | Ruff S113 | request with no timeout | `api/services/database_api.py` 7 calls | Fixed, 10 second timeout | a stalled database call could hang the API |
| student-2 | detect-secrets | 73 Google Maps photo references | `db/init_db.py` | Not fixed, in baseline | public image references, not secrets |
| student-2 | pip-audit | vulnerable Flask, flask-cors, requests and unpinned requests | `api`, `db`, `tests` requirements | Fixed, pins upgraded | known vulnerabilities |
| student-3 | Ruff S104 | binds to all interfaces | `api/app.py` 618, `db/app.py` 350 | Not fixed, `noqa` | other containers must reach the service |
| student-3 | Ruff S608 | SQL built from a string | `db/app.py` 171, 320 | Not fixed, `noqa` | column names come from a fixed list and values are bound |
| student-3 | Ruff S310 | `urlopen` allows any URL scheme | `tests/smoke_test.py` 30, 34, 117, 119 | Not fixed, `noqa` | URL is a fixed local address |
| student-3 | pip-audit | vulnerable Flask, flask-cors, requests | `api`, `db` requirements | Fixed, pins upgraded | known vulnerabilities |
| student-4 | Ruff S104 | binds to all interfaces | `api/app.py` 769, `db/app.py` 314 | Not fixed, `noqa` | other containers must reach the service |
| student-4 | Ruff S608 | SQL built from a string | `db/init_db.py` 168, `tests/test_init_db.py` 172, 176 | Not fixed, `noqa` | only placeholders or fixed table names are formatted and values are bound |
| student-4 | Ruff S603 | subprocess call | `tests/test_init_db.py` 22 | Not fixed, `noqa` | runs the seed script with the current interpreter |
| student-4 | Ruff S105, S106 | password in code | `tests/smoke_test.py` 53, 54, 224, 884, 937 | Not fixed, `noqa` | test account passwords, and line 937 is an error message |
| student-4 | detect-secrets | test passwords | `tests/smoke_test.py` 53, 54, 937 | Not fixed, in baseline | test account passwords |
| student-4 | pip-audit | vulnerable Flask, flask-cors, requests, Werkzeug, pytest and unpinned requests | `api`, `db`, `tests` requirements | Fixed, pins upgraded | known vulnerabilities |
| student-5 | Ruff S104 | binds to all interfaces | `api/app.py` 541, `db/app.py` 364 | Not fixed, `noqa` | other containers must reach the service |
| student-5 | Ruff S608 | SQL built from a string | `db/app.py` 47, 143, 199, 240, `db/init_db.py` 114 | Not fixed, `noqa` | table names, columns and search clauses are fixed and values are bound |
| student-5 | Ruff S310 | `urlopen` allows any URL scheme | `tests/smoke_test.py` 35, 40 | Not fixed, `noqa` | URL is a fixed local address |
| student-5 | pip-audit | vulnerable Flask, flask-cors, requests | `api`, `db` requirements | Fixed, pins upgraded | known vulnerabilities |
| shared | Ruff S104 | binds to all interfaces | `api/app.py` 238, `db/app.py` 548 | Not fixed, `noqa` | other containers must reach the service |
| shared | Ruff S608 | SQL built from a string | `db/app.py` 167 | Not fixed, `noqa` | column names come from a fixed list and values are bound |
| shared | Ruff S105 | password in code | `db/init_db.py` 97 | Not fixed, `noqa` | documented demo seed password |
| shared | detect-secrets | documented demo seed password | `db/init_db.py` 97 | Not fixed, in baseline | documented demo seed password |
| shared | pip-audit | vulnerable Flask, flask-cors, requests, Werkzeug | `api`, `db` requirements | Fixed, pins upgraded | known vulnerabilities |
| ai-services | Ruff S104 | binds to all interfaces | `ai-mode/app.py` 178, `mcp-server/server.py` 122, `multi-agent-server/server.py` 305, `rag-server/server.py` 268 | Not fixed, `noqa` | containers reach these host services through host.docker.internal |
| ai-services | Ruff S603, S607 | subprocess call by program name | `agentic-loop/release2_collectors.py` 93, 94 | Not fixed, `noqa` | fixed gh command with no shell, checked on PATH first |
| ai-services | pip-audit | vulnerable Flask, flask-cors, requests | all five service requirements | Fixed, pins upgraded | known vulnerabilities |
| scripts | Ruff S603, S607 | subprocess call | `smoke_test.py` 165, 187, 214, 295, `fetch_assets.py` 57, 58 | Not fixed, `noqa` | fixed command with no shell |
| scripts | Ruff S310 | `urlopen` allows any URL scheme | `smoke_test.py` 57, 62 | Not fixed, `noqa` | URL is a fixed local address |
| security | Ruff S603 | subprocess call in the new scan files | `run_scan.py` 22, `tests/test_pip_audit.py` 17, `tests/test_secrets.py` 26 | Not fixed, `noqa` | fixed command with no user input |

### Student 1
Findings: Ruff and pip-audit findings, listed in the table above.

Resolution: Confirmed the dependency upgrades: Flask 3.1.3, flask-cors 6.0.5,
requests 2.34.2 and pytest 9.1.1 across the `api`, `db` and `tests`
requirements. The two S104 findings are acceptable because both services must
listen on all interfaces for other containers to reach them. The four S608
findings build only column names, from the fixed `TRIP_FIELDS` and `DAY_FIELDS`
lists, and bind every value as a parameter, so user input never reaches the
SQL text. A rescan of the whole repository on 23 October passed all three
hooks, and the student-1 smoke test and post-commit endpoint tests gave the
same result before and after.

### Student 2
Findings: Ruff, detect-secrets and pip-audit findings, listed in the table above.

Resolution: Confirmed the dependency upgrades and the addition of 10-second timeouts to the seven database API calls. The S104 findings are acceptable because the services must listen on all interfaces for container-to-container communication. The S608 findings use fixed column lists and parameterised values. The 73 Google Maps photo references are public image identifiers, not credentials, and remain in the shared secrets baseline. The shared security tests and student-2 regression checks passed during local validation.

### Student 3
Findings: Ruff and pip-audit findings, listed in the table above.

Resolution: _student-3 to fill in: fixed, or reason this is acceptable as is_

### Student 4
Findings: Ruff, detect-secrets and pip-audit findings, listed in the table above.

Resolution: Every pin was upgraded to a fixed version and requests was pinned. The rest are false positives, each marked with `noqa` and its reason. Both services bind to all interfaces so other containers can reach them. The SQL formats only placeholders or fixed table names and binds every value. The subprocess call runs the seed script with the current interpreter. The passwords belong to test and documented demo accounts and are recorded in the baseline as reviewed. All student-4 tests gave the same result before and after.

### Student 5
Findings: Ruff and pip-audit findings, listed in the table above.

Resolution: _student-5 to fill in: fixed, or reason this is acceptable as is_

---

## Multi-Agent Workflow Evidence

### The shared Multi-Agent Server

One Multi-Agent Server, built by Caroline Zhou (student 1), serves all five
features. It runs on the host on port 5600, like AI-Mode, MCP and RAG, and is
not a Docker Compose service. Each feature's backend/API calls it, never the
page directly, so every workflow follows the Release 2 design flow:

```
Frontend UI -> Backend/API -> Multi-Agent Server -> Planner -> Worker -> Reviewer
            -> Human Review -> Response to Frontend UI
```

| Step | What it does |
|---|---|
| Planner | Reads the task, chooses the evidence sources (MCP tool calls, RAG retrieval, or data the backend supplied) and writes steps and acceptance criteria |
| Evidence | The server fetches only the sources the Planner chose and numbers them E1, E2 and so on |
| Worker | Answers from that evidence only, citing each claim as [E1], [E2] |
| Reviewer | A model review against each acceptance criterion, plus deterministic checks in code that every cited item exists and that something is cited |
| Human | Approve, correct (the Worker and Reviewer re-run with the feedback), partially accept, or reject. Nothing is released before this step |

Every agent reaches the model through AI-Mode, so no agent holds its own model
client. Each workflow is saved as a JSON record, and every step any agent or
person takes is appended to an audit log, `audit.jsonl`. That log is the
coordination evidence below.

### One workflow per feature

On 23 October the integrated application was rebuilt locally and one workflow
was started through each feature's own backend/API route, the same route its
Agents tab uses. Each was then given a human decision.

| Feature | Route | Evidence the Planner used | Reviewer | Human decision |
|---|---|---|---|---|
| 1 Trips & Itinerary | `POST /ai/agents` | E1 MCP `get_trip_itinerary`, E2 RAG passages | concerns: no citations | Correct, then approve |
| 2 Attractions & Dining | `POST /agents/workflows` | E1-E3 supplied Sydney places | pass | Approve |
| 3 Travel Mate | `POST /ai/multi-agent` | E1 supplied open trips by other travellers | concerns: cites E2, which does not exist | Reject |
| 4 Travel Guides | `POST /ai/agents` | E1-E2 supplied Kyoto guide facts, E3 MCP `lookup_destination_guide` | pass | Approve |
| 5 Bookings & Budget | `POST /agents/workflows` | E1 supplied bookings and budget for trip 1 | concerns: no citations | Reject |

Each first round took between 22 and 40 seconds on `llama3.2` running locally.

The workflows show the review steps working as designed:

- **Correction loop (student 1).** The first answer summarised the trip
  accurately but cited nothing, and the Reviewer raised a concern. The human
  correction asked for citations. The Worker re-ran, the second answer cited
  E1, the Reviewer passed it, and it was approved.
- **Invented citation caught (student 3).** The Worker recommended a Reykjavik
  campervan trip for a beach companion request and cited E2, but the
  workflow only had E1. The citation check flagged it in code, and the human
  rejected it.
- **Wrong arithmetic stopped (student 5).** The answer gave a total that did not
  match its own breakdown and named the wrong booking as the most expensive.
  The Reviewer flagged that nothing was cited, and the human rejected it,
  so the answer was never released.

The audit log for each workflow records every step in order. A single-round
workflow logs 12 entries:

```
created -> planner plan -> server evidence -> worker response -> reviewer review
-> human decision
```

Each of these steps also logs a status change. Student 1's corrected workflow
logs 18 entries, with the second Worker and Reviewer round between the two
human decisions.

### Multi-Agent Workflow Review

The shared agentic loop's Multi-Agent Workflow Review mode then read every
workflow and audit log on the server. Its pass/fail verdicts are decided in
code, not by the model. The full record is in
`docs/evidence/agentic-loop-release2-multiagent-mode.md`.

| Result | Check |
|---|---|
| PASS | The Multi-Agent Server is not a Docker Compose service |
| PASS | Agents reach the model only through AI-Mode |
| PASS | Integrated through backend/API and page: students 1 to 5 |
| PASS | All 5 validation probes refused with the expected status |
| PASS | No workflow reached a final status without a human decision |
| PASS | Audit log complete and in order for all 15 workflows |
| PASS | Every Planner and Reviewer reply parsed, with no fallbacks |
| WARN | 10 of 17 Worker responses failed the citation checks |
| WARN | Humans approved 2 responses the Reviewer had flagged |

The 15 workflows are the five above plus ten earlier student-1 development runs
from 9 October. Seven of those had been left awaiting review, and they were
rejected as stale before the review ran.

Both warnings come mostly from those early runs. Of the 10 citation failures,
3 are in the five workflows above: student 1's first round, student 3 and
student 5. Two of those were rejected, and student 1's was corrected. Both
approvals over a Reviewer concern are 9 October runs. No workflow from 23
October was approved over a concern.

The model's own written summary of the review listed some items as "not
shown" even though the coded checks cover them. This is why the verdicts are
computed in code: the local 3B model can explain a verdict but misreads
detailed evidence.

## Multi-Agent Integration, Student 4 (Travel Guides)

The Agents tab takes a task about a destination, such as a pre-trip briefing, with three suggested tasks. The city comes from an optional field or from the task text, and a tick box offers the RAG knowledge base. `student-4-api` sends the shared Multi-Agent Server the guide's currency, transport, visa, weather and safety facts as supplied evidence, plus one `lookup_destination_guide` MCP call. The Planner, Worker and Reviewer run on the server and the workflow stops at human review. The person approves, corrects, partly accepts or rejects it in the tab, and a recent workflows list reopens past runs with their audit log.

The client is `services/multi_agent_client.py` and the routes are in `routes/ai_agents.py`. Like the MCP and RAG clients, a `MULTI_AGENT_ENABLED=false` setting returns a notice with no network call and no database read. An unreachable server returns a 503 notice. In the cloud's async mode the run card refreshes itself until it reaches human review. Twenty five unit tests in `tests/test_agents.py` cover the disabled, unavailable, refusal and decision paths with stubbed servers. The tab reflows for tablet and mobile widths.

## Student 4 Local Deployment

With AI-Mode, MCP, RAG and the Multi-Agent Server running on the host and `student-4-api` built with every flag on, one Agents workflow ran from Planner through Evidence, Worker and Reviewer to human review in about 26 seconds. Its three evidence items were all fetched and the Reviewer passed it. A rejection without notes was refused, a correction re-ran the Worker with the feedback, a partial acceptance released the edited text, and a second decision on the closed workflow returned a 409. The audit log recorded every step. The Guides, AI Assistant, MCP and Ask tabs and the student-4 smoke test still passed alongside it.

## Student 4 Cloud Behaviour

The cloud baseline switches AI-Mode, MCP, RAG and Multi-Agent off. Every student-4 integration reads its own flag in one client module, and the frontend holds no service address, so nothing assumes a host service is running. With `student-4-api` started with all four flags false, the Guides tab, sign in and live rates worked and MCP, Ask and Agents each returned a notice with no call made. The AI Assistant answered a named month or a currency conversion from the guide and linked the guide for anything else. `PUBLIC_BASE_URL` is set by the deploy script so email links do not point at localhost, and email goes out through Resend as described below.

## Student 4 Email Delivery

Sign-up verification and password reset need a real inbox in the cloud, and Mailpit is only reachable on the VM. `student-4-api` now sends every email through one function that reads `MAIL_PROVIDER`. The default is SMTP to Mailpit, so local runs and CI are unchanged. Setting it to `resend` posts to the Resend API from a sender on a verified domain. The settings reach the container through `docker-compose.yml` and `deploy_remote.sh`, which reads them from a private file on the VM with mode 600, so the key is never in git, in a workflow or on a command line. Without that file the app keeps using Mailpit. A refused or timed out send returns the existing 503 notice and never shows Resend's reason to the user. Eight unit tests cover both providers.

## Student 4 CI Testing

`student-4.yml` runs in two stages. The pre-commit stage runs all ten unit test files with pytest before anything is built, and each stubs its services. The post-commit stage starts the containers and tests two endpoint functions over HTTP, `list_guides` (`GET /guides`) and `start` (`POST /ai/agents`), with five tests in `tests/test_endpoints.py`. The start tests cover task validation and the notice shown when `MULTI_AGENT_ENABLED` is false. The workflow publishes the results as a JUnit file, a job summary table and an uploaded artifact.

---

## Bonus: Cloud Extension

The required cloud deployment keeps AI-Mode, MCP, RAG and the Multi-Agent
Server off by default. `cloud-deployment.yml` sets all four flags to `false`
unless a person runs it manually with `enable_cloud_ai=true`, and its smoke test
fails if any flag is wrong for the mode chosen. The bonus items below build on
that baseline. They do not replace it.

### B1-B4: shared AI services in the cloud

Kevin Kim (student 2) built the cloud AI profile. With `enable_cloud_ai=true`,
`deploy/azure/configure_ai.sh` installs Ollama with `llama3.2:latest` and runs
AI-Mode, MCP, RAG and the Multi-Agent Server as four systemd units on the VM,
`nextstop-ai@<service>`. Each restarts on failure. They run on the host, not in
Docker, as they do locally. Ollama listens on `127.0.0.1` only and serves one
request at a time, so one shared model handles all five features.

Generation on the VM's two CPUs is slow. A full Planner, Worker and Reviewer
run took longer than the 240 second HTTP timeout. In the cloud the Multi-Agent
Server therefore runs asynchronously (`MULTI_AGENT_ASYNC_ENABLED`): `POST
/workflows` returns 202 straight away, one background worker runs workflows in
order from a bounded queue, and the page reads the workflow by ID. After a
restart, any workflow still in progress is marked failed rather than run again,
so no decision is ever replayed. The Worker and Reviewer each have 360 seconds.

After deploying, `tests/cloud/check_cloud_ai.py` runs live checks on the VM
through each feature's own backend/API, not by calling the AI services
directly. The latest run, from the push to main on 23 October, passed all 14
checks in about 21 minutes:
<https://github.com/aurelia-sari/ads-assignment/actions/runs/39883876495>

| Bonus | What the check requires | Features | Result |
|---|---|---|---|
| B1 Cloud AI-Mode | The app returns a real model answer, not the fallback text | student 1 | PASS |
| B2 Cloud MCP | A JSON-RPC `tools/call` through the app returns the tool's result | students 1-5 | 5 PASS |
| B3 Cloud RAG | Retrieval has hits above "insufficient", the answer is not refused, and its citation list names a retrieved source | students 1-5 | 5 PASS |
| B4 Cloud Multi-Agent | The workflow belongs to this run, and its audit log shows planner plan, then worker response, then reviewer review, in order | students 1-3 | 3 PASS |

The B4 check closes its own test workflows by rejection, so test output is
never approved for release, and the append-only audit log keeps them.
Students 4 and 5 added their Agents tabs after the check was written, so it
does not yet cover them. Their Planner, Worker and Reviewer workflows are
shown locally in the Multi-Agent Workflow Evidence section.

### B5: cloud endpoint security

Only the frontends are public. Every other service is reachable only from the
VM itself.

| Control | Where it is set |
|---|---|
| The network security group allows only SSH (22), the home page (80) and the frontends (8080-8085) | `deploy/azure/provision.sh`, Aung Ko Khaing (student 5) |
| Every backend/API, database and Mailpit port is bound to `127.0.0.1` on the VM | `docker-compose.cloud.yml` |
| AI-Mode, MCP, RAG, the Multi-Agent Server and Ollama listen only on the VM | `deploy/azure/configure_ai.sh` |

Tanishpreet Kour (student 3) checked this from outside the VM. All seven
frontend ports return 200. Every API and database port (5000, 5101-5105,
5200-5205), Mailpit (8025), and every AI port (5300, 5400, 5500, 5600, 11434)
gets no connection. The results are in `evidence/cloud/endpoint_exposure.txt`,
`evidence/cloud/endpoint_exposure_ai_ports.txt` and
`evidence/cloud/nsg_rules.txt`.

### B6: cloud data security

| Control | Evidence |
|---|---|
| SSH accepts keys only, with password login disabled | `evidence/cloud/data_security.txt` |
| The VM disk is encrypted at rest with a platform-managed key | `evidence/cloud/data_security.txt` |
| The VM address and deploy key are GitHub Actions secrets, never in git, and the workflow has read-only repository permissions | `.github/workflows/cloud-deployment.yml` |
| The email provider key lives in a file on the VM readable only by its owner (mode 600), never in git, a workflow or a command line | Student 4 Email Delivery section |
| Databases sit in Docker volumes that only the containers on the VM can reach, and the volumes survive redeploys | `docker-compose.yml`, B5 above |
| The model name given to the deploy is checked against a strict pattern before use, so it cannot inject shell commands | `deploy/azure/configure_ai.sh` |
| detect-secrets blocks any commit that adds a credential | Pre-Commit Security Testing section |

### Limitations

Some of these protections are Azure defaults rather than controls the team
built: disk encryption with a platform key, and key-only SSH from `az vm
create`. The team verified both and recorded the results. The deployment also
lacks three things a production system would have:

- **HTTPS.** The app is served over plain HTTP on the VM's IP address. A domain
  and a reverse proxy with a TLS certificate would be the next step.
- **Authentication in front of the endpoints.** Only the application's own
  sign-in protects them.
- **A restricted SSH source.** SSH accepts connections from any address,
  because GitHub's hosted runners have no fixed IP. A self-hosted runner or
  Azure Bastion would allow narrowing it.
