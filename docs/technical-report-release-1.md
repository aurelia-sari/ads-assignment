# Release 1 Technical Report - Group 25

**41026 Advanced Software Development, Spring 2026**
**Project: NextStop - Agentic AI travel planning application**

> Working draft. Export to PDF for submission as `group-25.pdf`.
> **Canvas accepts ONE group PDF, submitted by one person.** A duplicate group
> submission will not be marked.
>
> **Due: 4 October 2026, 11:59 PM AEST.**
>
> Section numbers below map 1:1 to the eight report sections in the Release 1
> brief, section 4. Sections marked **(Individual)** need one subsection per
> student; a missing individual subsection costs that student marks, not the
> group.
>
> **All five students must attend the Week 9 showcase. Non-attendance is 0.**

**GitHub Repository:** https://github.com/aurelia-sari/ads-assignment.git
**Showcase video:** _TODO - max 10 minutes_

---

## 1. Project overview and Release 1 scope

_Concise overview of the Release 0 application, then what Release 1 adds.
Must clearly separate each student's responsibilities from shared group ones._

### 1.1 Release 0 in brief

_2-3 paragraphs. Five features, each three containerised microservices; shared
AI-Mode; the two standing rules (each DB owns its schema; only AI-Mode talks to
Ollama)._

### 1.2 What Release 1 adds

| Addition | Kind | Owner |
|----------|------|-------|
| Shared local MCP server (:5400) | Group | Caroline |
| Shared local RAG server (:5500) | Group | Caroline |
| Agentic loop MCP + RAG validation modes | Group | Caroline |
| De-containerising AI-Mode, MCP, RAG, loop | Group | Caroline |
| MCP + RAG access from each feature's frontend via its backend/API | Individual | All five |
| `student-x.yml` updated, MCP/RAG disabled in CI | Individual | All five |

### 1.3 The containerisation boundary

_The key structural change. Release 1 requires AI-Mode, MCP, RAG and the agentic
loop to run on the host and NOT appear as docker-compose services. Explain
host.docker.internal in one direction, localhost in the other._

### 1.4 Per-student Release 1 scope **(Individual)**

_One short subsection per student: what their feature gained._

- **student-1 - Caroline Zhou (Trips & Itinerary)** - _draft below, use as the shape_
- **student-2 - Kevin Kim (Attractions & Dining)** - _TODO_
- **student-3 - Tanishpreet Kour (Travel Mate)** - _TODO_
- **student-4 - Aurelia Sari (Accounts & Guides)** - _TODO_
- **student-5 - Aung Ko Khaing (Bookings & Budget)** - _TODO_

---

## 2. Release 1 requirements

_Functional requirements. Number them R1-n so validation in section 6 can cite
them._

### 2.1 Shared MCP server

| ID | Requirement |
|----|-------------|
| R1-1 | Runs locally, non-containerised, not a compose service |
| R1-2 | Exposes a registry of tools over JSON-RPC (`tools/list`, `tools/call`) |
| R1-3 | Accepts valid requests and returns structured results |
| R1-4 | Enforces declared tool boundaries and refuses calls that cross them |
| R1-5 | Every feature can invoke tools via its frontend UI through its backend/API |

### 2.2 Shared RAG server

| ID | Requirement |
|----|-------------|
| R1-6 | Runs locally, non-containerised, not a compose service |
| R1-7 | Retrieves relevant project context for a question |
| R1-8 | Generates answers grounded in retrieved context only |
| R1-9 | Every answer carries source citations |
| R1-10 | Every answer carries a confidence category |
| R1-11 | Returns an insufficient-context response when nothing relevant is retrieved |

### 2.3 Per-feature integration and the agentic loop

| ID | Requirement |
|----|-------------|
| R1-12 | Each feature's frontend reaches MCP and RAG only through its own backend/API |
| R1-13 | Release 0 functionality and AI-Mode keep working after the extension |
| R1-14 | Agentic loop gains separate MCP and RAG validation modes |
| R1-15 | Loop runs locally, non-containerised, and produces output for both modes |
| R1-16 | MCP and RAG integration retained but disabled during CI/CD |

---

## 3. Non-functional requirements

_The brief names nine areas and asks for measurable requirements where
practical. One row each; add the measure, not just the aspiration._

| # | Area | Requirement | How it is measured |
|---|------|-------------|--------------------|
| N1 | Security | _TODO_ | |
| N2 | MCP tool boundaries | Every tool call is read-only, allowlisted, schema-checked and row-capped | 6 boundary probes in the loop's MCP mode, each must be refused at the expected boundary |
| N3 | RAG grounding and traceability | Every grounded answer cites the passages it used | Citations non-empty whenever `grounded=true`; retrieval checks assert the top source |
| N4 | Reliability | _TODO_ | |
| N5 | Performance | _TODO - measure a /ask round trip locally_ | |
| N6 | Usability | _TODO_ | |
| N7 | Maintainability | _TODO_ | |
| N8 | Interoperability | _TODO_ | |
| N9 | Availability | _TODO - behaviour when a local AI service is down_ | |

---

## 4. Release 1 architecture

_Required: overall architecture diagram showing components, connections and the
containerisation boundary._

- [ ] `docs/diagrams/release-1-architecture.mmd` - **TODO**
- [ ] Updated repository structure (mirror the README tree)

_Prose: what is containerised, what is not, and how the two halves connect._

---

## 5. MCP and RAG design

_Required: a flow diagram covering frontend/backend interactions, the RAG
retrieval and grounded-response process, and the MCP tool layer._

- [ ] `docs/diagrams/mcp-rag-flow.mmd` - **TODO**

### 5.1 Registered MCP tools

| Tool | Owner | Reads from | Required args | Row limit |
|------|-------|-----------|---------------|-----------|
| `list_trips` | student-1 | student-1-db | none | 20 |
| `get_trip_itinerary` | student-1 | student-1-db | `trip_id` | 30 |
| `search_places` | student-2 | student-2-db | none | 20 |
| `find_travel_mates` | student-3 | student-3-db | none | 20 |
| `lookup_destination_guide` | student-4 | student-4-db | `query` | 20 |
| `search_flights` | student-5 | student-5-db | none | 20 |

### 5.2 Tool boundaries

| Boundary | Rule |
|----------|------|
| `registered` | The tool must exist in the registry |
| `read-only` | Only GET is issued upstream; `boundaries.py` offers no write path |
| `allowlisted` | The target must be the service the tool declared |
| `schema-checked` | Arguments must match the declared input schema |
| `capped` | Results truncated to the tool's row limit |

### 5.3 RAG retrieval and grounding

_Knowledge sources: 7 curated markdown files, 31 chunks. BM25, no embedding
model - justify: explainable citations, instant start on 8 GB, no extra model
dependency._

**Confidence categories** - computed from retrieval scores, not asked of the
model, because a small local model answers "high" almost unconditionally.

| Category | Rule |
|----------|------|
| `high` | top score >= 7.0, coverage >= 50%, >= 2 corroborating passages |
| `medium` | top score >= 4.0 **and** coverage >= 40% |
| `low` | above the 2.5 relevance floor but below medium |
| `insufficient` | nothing clears the relevance floor - no model call is made |

---

## 6. Validation and results

_Required evidence, all three bullets:_

### 6.1 MCP and RAG through every feature's frontend UI and backend/API **(Individual)**

_One screenshot pair per student: an MCP tool result, and a grounded RAG answer
showing citations + confidence._

| Student | MCP interaction | RAG interaction |
|---------|-----------------|-----------------|
| student-1 | ✅ captured | ✅ captured |
| student-2 | ⬜ TODO | ⬜ TODO |
| student-3 | ⬜ TODO | ⬜ TODO |
| student-4 | ⬜ TODO | ⬜ TODO |
| student-5 | ⬜ TODO | ⬜ TODO |

### 6.2 Local terminal validation

_`curl` transcripts against :5400 and :5500 - health, tools/list, a tool call, a
boundary refusal, a grounded answer, an insufficient-context answer._

### 6.3 Agentic loop, both validation modes

- `docs/evidence/agentic-loop-release1-mcp-mode.md` - all 6 tools returned rows;
  all 6 boundary probes refused at the expected boundary
- `docs/evidence/agentic-loop-release1-rag-mode.md` - 5/5 retrieval checks hit
  the expected source; both insufficient-context checks correctly refused

### 6.4 Successful `student-x.yml` runs with MCP/RAG disabled **(Individual)**

| Workflow | Run link |
|----------|----------|
| student-1.yml | ⬜ TODO |
| student-2.yml | ⬜ TODO |
| student-3.yml | ⬜ TODO |
| student-4.yml | ⬜ TODO |
| student-5.yml | ⬜ TODO |

### 6.5 Deployment via the Release 0 docker-compose.yml

_Show compose still deploys all 18 containers, and that the backends carry the
MCP/RAG connection configuration while neither is a compose service._

---

## 7. Individual contributions **(Individual)**

_One log per student: feature updates, Release 1 work, integration and
validation activity, and identifiable commits._

| Student | Contribution | Commits |
|---------|-------------|---------|
| student-1 Caroline Zhou | Shared MCP + RAG servers, loop validation modes, de-containerisation, student-1 wiring | _TODO: list_ |
| student-2 Kevin Kim | _TODO_ | |
| student-3 Tanishpreet Kour | _TODO_ | |
| student-4 Aurelia Sari | _TODO_ | |
| student-5 Aung Ko Khaing | _TODO_ | |

---

## 8. Repository and showcase links

- **Repository:** https://github.com/aurelia-sari/ads-assignment.git
- **Showcase video:** _TODO_ (max 10 min; must show MCP + RAG through every
  feature's UI, terminal validation of both servers, and the loop in both modes)

---

## 9. Known issues and limitations

_Carry the Release 0 table format. Seeded from what Release 1 has already
surfaced:_

| ID | Issue | Likelihood | Impact | Mitigation | Owner |
|----|-------|-----------|--------|------------|-------|
| R1-A | The loop's OBSERVE step sometimes asserts facts not present in the collected evidence - one MCP run claimed `allow: get` appears in `nginx.conf`, which it never saw. The ACT evidence is collected by code and is accurate; the model's commentary drifts | Occasional | Low | Read ACT evidence as authoritative; OBSERVE is commentary. A larger review model reduces it | Caroline |
| R1-B | BM25 retrieval matches terms, not meaning - a question phrased entirely in synonyms of the corpus wording can fall below the relevance floor and be refused despite being covered | Occasional | Medium | Confidence and the refusal are honest about it; an embedding retriever is the fix if it proves to matter | Caroline |
| R1-C | The local AI services must be started separately from `docker compose up`. `dev.sh up` does it, but starting compose by hand leaves every AI path failing | Certain, by design | Low | Required by the brief - they cannot be compose services. Frontends show a clear unreachable notice naming the fix | Group |
| R1-D | _TODO - add per-feature limitations_ | | | | |

---

## Appendix A: local execution constraints

_Required by the brief: "local execution constraints for MCP, RAG, and the
agentic loop". Ports 5300/5400/5500, the host venv, the one-`.env`-two-
perspectives rule, Ollama on 8 GB._
