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

Resolution: _student-1 to fill in: fixed, or reason this is acceptable as is_

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

## Multi-Agent Integration, Student 4 (Travel Guides)

The Agents tab takes a task about a destination, such as a pre-trip briefing, with three suggested tasks. The city comes from an optional field or from the task text, and a tick box offers the RAG knowledge base. `student-4-api` sends the shared Multi-Agent Server the guide's currency, transport, visa, weather and safety facts as supplied evidence, plus one `lookup_destination_guide` MCP call. The Planner, Worker and Reviewer run on the server and the workflow stops at human review. The person approves, corrects, partly accepts or rejects it in the tab, and a recent workflows list reopens past runs with their audit log.

The client is `services/multi_agent_client.py` and the routes are in `routes/ai_agents.py`. Like the MCP and RAG clients, a `MULTI_AGENT_ENABLED=false` setting returns a notice with no network call and no database read. An unreachable server returns a 503 notice. In the cloud's async mode the run card refreshes itself until it reaches human review. Twenty five unit tests in `tests/test_agents.py` cover the disabled, unavailable, refusal and decision paths with stubbed servers. The tab reflows for tablet and mobile widths.
