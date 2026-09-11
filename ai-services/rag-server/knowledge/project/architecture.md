# NextStop architecture

NextStop is a microservices application built by Group 25 for 41026 Advanced
Software Development. Five students each own three containerised
microservices: a frontend, a backend/API, and a database service.

## Request flow

A normal page interaction flows browser -> shared-frontend -> student frontend
-> student backend/API -> student database service. An AI interaction flows
frontend -> backend/API -> AI-Mode -> Ollama -> the local LLM.

## Two standing rules

Each database service owns its own schema. No service opens another service's
SQLite file; cross-feature data is fetched over HTTP from the owning database
API. In each backend/API every database call lives in one module, so this stays
checkable rather than merely intended.

No service talks to Ollama directly. Model selection, prompt loading and AI
error handling all live in the shared AI-Mode service, so there is one place to
change the model and one place where AI failures are handled.

## Shared services

`shared-frontend` serves the unified home page on port 8080 and reverse-proxies
every student frontend, so all five features are reachable from one origin and
HTMX never makes a cross-origin request. `shared-api` provides cross-feature
reads. `shared-db` holds accounts and traveller records.
