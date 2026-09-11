# Release 1 scope

Release 1 extends the Release 0 application with a shared local MCP server, a
shared local RAG server, and an agentic loop that can validate both.

## What is containerised and what is not

The Release 0 docker-compose configuration continues to run the containerised
feature microservices: each student's frontend, backend/API and database
service, plus the shared frontend, shared API and shared database.

AI-Mode, the MCP server, the RAG server and the agentic loop are not
containerised and are not docker-compose services. They run on the host, and
the containerised backends reach them through `host.docker.internal`.

## The MCP server

The shared MCP server exposes a registry of read-only tools over JSON-RPC. Each
tool declares the single database service it may read from, a schema for its
arguments, and a row limit. Four boundaries are enforced on every call: the
call must be read-only, the target must be allowlisted, the arguments must
match the declared schema, and the result set is capped.

## The RAG server

The shared RAG server retrieves from a curated markdown knowledge base using
BM25, and asks the local model to answer using only the retrieved chunks. Every
answer carries source citations and a confidence category. When retrieval finds
nothing relevant, the server returns an insufficient-context response and does
not call the model at all.

## Confidence categories

Confidence is `high`, `medium` or `low`, and is derived from the retrieval
scores rather than from the model's own self-assessment. A model asked how
confident it is will tend to say "very", which is exactly why the figure is
computed from the evidence instead.
