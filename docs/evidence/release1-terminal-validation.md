# Release 1 terminal validation - MCP and RAG servers

Captured 2026-09-28 15:46 on localhost, commit `45b6510` (main).
Both servers run on the host, not in Docker (`./scripts/ai_services.sh up`); the
containerised application was started with `./scripts/dev.sh up`. Local model: `llama3.2:latest` via Ollama, reached only through AI-Mode.

Sections 1-2 call the servers directly from the host terminal. Section 3 calls
them the way the frontend does, through student-1-api. Section 4 confirms the
Release 0 feature still works. Section 5 shows the compose deployment.


## 1. MCP server (localhost:5400)


### 1.1 Health

```console
$ curl -s localhost:5400/health
```

```json
{
  "containerised": false,
  "protocol_version": "2024-11-05",
  "registered_tools": 6,
  "service": "mcp-server",
  "status": "running"
}
```


### 1.2 Registered tools (`tools/list`)

```console
$ curl -s localhost:5400/mcp -H 'Content-Type: application/json' -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
```

```json
{
  "id": 1,
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "description": "Find open trip posts from travellers looking for a travel mate.",
        "inputSchema": {
          "properties": {
            "destination": {
              "description": "Partial destination name.",
              "maxLength": 60,
              "type": "string"
            },
            "status": {
              "description": "Post status to filter on.",
              "enum": [
                "open",
                "matched",
                "closed"
              ],
              "type": "string"
            }
          },
          "required": [],
          "type": "object"
        },
        "name": "find_travel_mates",
        "owner": "student-3",
        "rowLimit": 20,
        "target": "student-3-db"
      },
      {
        "description": "Return one trip with its day-by-day itinerary.",
        "inputSchema": {
          "properties": {
            "trip_id": {
              "description": "The trip to fetch.",
              "minimum": 1,
              "type": "integer"
            }
          },
          "required": [
            "trip_id"
          ],
          "type": "object"
        },
        "name": "get_trip_itinerary",
        "owner": "student-1",
        "rowLimit": 30,
        "target": "student-1-db"
      },
      {
        "description": "List planned trips, optionally filtered by destination or status.",
        "inputSchema": {
          "properties": {
            "destination": {
              "description": "Partial destination name, e.g. 'Tokyo'.",
              "maxLength": 60,
              "type": "string"
            },
            "status": {
              "description": "Trip status to filter on.",
              "enum": [
                "planned",
                "booked",
                "completed"
              ],
              "type": "string"
            }
          },
          "required": [],
          "type": "object"
        },
        "name": "list_trips",
        "owner": "student-1",
        "rowLimit": 20,
        "target": "student-1-db"
      },
      {
        "description": "Look up travel-guide destinations by city or country.",
        "inputSchema": {
          "properties": {
            "query": {
              "description": "Partial city or country name.",
              "maxLength": 60,
              "type": "string"
            }
          },
          "required": [
            "query"
          ],
          "type": "object"
        },
        "name": "lookup_destination_guide",
        "owner": "student-4",
        "rowLimit": 20,
        "target": "student-4-db"
      },
      {
        "description": "Search available flights by origin, destination and budget ceiling.",
        "inputSchema": {
          "properties": {
            "budget_aud": {
              "description": "Maximum fare in AUD.",
              "maximum": 100000,
              "minimum": 1,
              "type": "integer"
            },
            "destination": {
              "description": "Partial destination city.",
              "maxLength": 60,
              "type": "string"
            },
            "origin": {
              "description": "Partial origin city.",
              "maxLength": 60,
              "type": "string"
            }
          },
... (34 more lines truncated)
```


### 1.3 Valid call: `list_trips` (input: `destination`)

```console
$ curl -s localhost:5400/mcp -H 'Content-Type: application/json' -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_trips", "arguments": {"destination": "Kyoto"}}}'
```

```json
{
  "id": 1,
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "text": "list_trips returned 1 row(s) from student-1-db",
        "type": "text"
      }
    ],
    "isError": false,
    "structuredContent": {
      "arguments": {
        "destination": "Kyoto"
      },
      "owner": "student-1",
      "row_count": 1,
      "rows": [
        {
          "budget_aud": 4200.0,
          "destination": "Kyoto, Japan",
          "end_date": "2026-05-03",
          "start_date": "2026-04-25",
          "status": "booked",
          "traveller_id": 1,
          "trip_id": 1,
          "trip_name": "Golden Week in Kyoto"
        }
      ],
      "source": "student-1-db",
      "tool": "list_trips",
      "truncated": false
    }
  }
}
```


### 1.4 Valid call: `get_trip_itinerary` (input: `trip_id`)

```console
$ curl -s localhost:5400/mcp -H 'Content-Type: application/json' -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_trip_itinerary", "arguments": {"trip_id": 1}}}'
```

```json
{
  "id": 1,
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "text": "get_trip_itinerary returned 1 row(s) from student-1-db",
        "type": "text"
      }
    ],
    "isError": false,
    "structuredContent": {
      "arguments": {
        "trip_id": 1
      },
      "owner": "student-1",
      "row_count": 1,
      "rows": [
        {
          "days": [
            {
              "activity": "Arrive, Gion evening walk",
              "day_date": "2026-04-25",
              "day_id": 1,
              "day_number": 1,
              "location": "Kyoto",
              "notes": "Drop bags at ryokan first",
              "trip_id": 1
            },
            {
              "activity": "Fushimi Inari at sunrise",
              "day_date": "2026-04-26",
              "day_id": 2,
              "day_number": 2,
              "location": "Kyoto",
              "notes": "Beat the crowds, go before 7am",
              "trip_id": 1
            },
            {
              "activity": "Bamboo grove and monkey park",
              "day_date": "2026-04-27",
              "day_id": 3,
              "day_number": 3,
              "location": "Arashiyama",
              "notes": "Half day, train from Kyoto",
              "trip_id": 1
            },
            {
              "activity": "Todai-ji and deer park day trip",
              "day_date": "2026-04-28",
              "day_id": 4,
              "day_number": 4,
              "location": "Nara",
              "notes": "45 min by local line",
              "trip_id": 1
            }
          ],
          "trip": {
            "budget_aud": 4200.0,
            "destination": "Kyoto, Japan",
            "end_date": "2026-05-03",
            "start_date": "2026-04-25",
            "status": "booked",
            "traveller_id": 1,
            "trip_id": 1,
            "trip_name": "Golden Week in Kyoto"
          }
        }
      ],
      "source": "student-1-db",
      "tool": "get_trip_itinerary",
      "truncated": false
    }
  }
}
```


### 1.5 Boundary refusal: unregistered tool

Refused at the `registered` boundary.

```console
$ curl -s localhost:5400/mcp -H 'Content-Type: application/json' -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "delete_trip", "arguments": {"trip_id": 1}}}'
```

```json
{
  "id": 1,
  "jsonrpc": "2.0",
  "result": {
    "boundary": "registered",
    "content": [
      {
        "text": "no registered tool named 'delete_trip'",
        "type": "text"
      }
    ],
    "isError": true
  }
}
```


### 1.6 Boundary refusal: argument fails the schema

`trip_id` must be an integer; refused at the `schema-checked` boundary.

```console
$ curl -s localhost:5400/mcp -H 'Content-Type: application/json' -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_trip_itinerary", "arguments": {"trip_id": "1; DROP TABLE trips"}}}'
```

```json
{
  "id": 1,
  "jsonrpc": "2.0",
  "result": {
    "boundary": "schema-checked",
    "content": [
      {
        "text": "argument 'trip_id' must be an integer",
        "type": "text"
      }
    ],
    "isError": true
  }
}
```


### 1.7 Boundary refusal: undeclared argument

```console
$ curl -s localhost:5400/mcp -H 'Content-Type: application/json' -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_trips", "arguments": {"sql": "SELECT * FROM trips"}}}'
```

```json
{
  "id": 1,
  "jsonrpc": "2.0",
  "result": {
    "boundary": "schema-checked",
    "content": [
      {
        "text": "unexpected argument(s): sql",
        "type": "text"
      }
    ],
    "isError": true
  }
}
```


## 2. RAG server (localhost:5500)


### 2.1 Health

```console
$ curl -s localhost:5500/health
```

```json
{
  "average_chunk_tokens": 44.4,
  "chunks": 31,
  "containerised": false,
  "retrieval": "bm25",
  "service": "rag-server",
  "source_count": 7,
  "sources": [
    "project/architecture.md",
    "project/release-1-scope.md",
    "travel/accounts-and-guides.md",
    "travel/attractions-and-dining.md",
    "travel/flights-hotels-budget.md",
    "travel/travel-mate-matching.md",
    "travel/trips-and-itineraries.md"
  ],
  "status": "running",
  "vocabulary": 608
}
```


### 2.2 Knowledge sources (`/index`)

```console
$ curl -s localhost:5500/index
```

```json
{
  "average_chunk_tokens": 44.4,
  "chunks": 31,
  "source_count": 7,
  "sources": [
    "project/architecture.md",
    "project/release-1-scope.md",
    "travel/accounts-and-guides.md",
    "travel/attractions-and-dining.md",
    "travel/flights-hotels-budget.md",
    "travel/travel-mate-matching.md",
    "travel/trips-and-itineraries.md"
  ],
  "vocabulary": 608
}
```


### 2.3 Retrieval only (`/search`)

Shows the BM25 scores the confidence category is computed from.

```console
$ curl -s localhost:5500/search -H 'Content-Type: application/json' -d '{"question": "How should I split a trip budget across days?"}'
```

```json
{
  "confidence": "high",
  "confidence_reason": "best score 7.0355 with 67% question coverage, corroborated by 4 passages",
  "hits": [
    {
      "chunk": 3,
      "coverage": 0.667,
      "excerpt": "The budget recorded against a trip is a total ceiling in AUD, not a per-day figure, and it is intended to cover flights, accommodation, food and activities together. As a planning rule of thumb for a mid-range traveller, allocate roughly 40...",
      "number": 1,
      "score": 7.0355,
      "section": "Budget guidance",
      "source": "travel/trips-and-itineraries.md"
    },
    {
      "chunk": 2,
      "coverage": 0.5,
      "excerpt": "An itinerary day belongs to exactly one trip and carries a day number, a calendar date, a location, and a planned activity. Day numbers start at 1 and should run consecutively to the length of the trip. A three-night trip has four itinerary...",
      "number": 2,
      "score": 6.4044,
      "section": "Itinerary days",
      "source": "travel/trips-and-itineraries.md"
    },
    {
      "chunk": 4,
      "coverage": 0.333,
      "excerpt": "Changing the destination of a `booked` trip is not supported. The intended path is to mark the existing trip `completed` or delete it, and create a new trip. Changing dates on a `booked` trip is allowed, but every itinerary day keeps its ow...",
      "number": 3,
      "score": 4.2952,
      "section": "Changing a trip after booking",
      "source": "travel/trips-and-itineraries.md"
    },
    {
      "chunk": 4,
      "coverage": 0.333,
      "excerpt": "A budget belongs to one trip and records a total in AUD alongside the amount committed by current selections. The remaining budget is the total minus the committed amount, and it is allowed to go negative - the traveller is warned rather th...",
      "number": 4,
      "score": 4.1342,
      "section": "Budget",
      "source": "travel/flights-hotels-budget.md"
    }
  ],
  "question": "How should I split a trip budget across days?"
}
```


### 2.4 Grounded answer (`/ask`)

```console
$ curl -s localhost:5500/ask -H 'Content-Type: application/json' -d '{"question": "How should I split a trip budget across days?"}'
```

```json
{
  "answer": "I can answer that based on [1]. According to the planning rule of thumb for a mid-range traveller, allocate roughly 40 per cent of a trip budget to flights, 30 per cent to accommodation, 20 per cent to food and activities, and keep 10 per cent as contingency.",
  "citations": [
    {
      "chunk": 3,
      "coverage": 0.667,
      "excerpt": "The budget recorded against a trip is a total ceiling in AUD, not a per-day figure, and it is intended to cover flights, accommodation, food and activities together. As a planning rule of thumb for a mid-range traveller, allocate roughly 40...",
      "number": 1,
      "score": 7.0355,
      "section": "Budget guidance",
      "source": "travel/trips-and-itineraries.md"
    },
    {
      "chunk": 2,
      "coverage": 0.5,
      "excerpt": "An itinerary day belongs to exactly one trip and carries a day number, a calendar date, a location, and a planned activity. Day numbers start at 1 and should run consecutively to the length of the trip. A three-night trip has four itinerary...",
      "number": 2,
      "score": 6.4044,
      "section": "Itinerary days",
      "source": "travel/trips-and-itineraries.md"
    },
    {
      "chunk": 4,
      "coverage": 0.333,
      "excerpt": "Changing the destination of a `booked` trip is not supported. The intended path is to mark the existing trip `completed` or delete it, and create a new trip. Changing dates on a `booked` trip is allowed, but every itinerary day keeps its ow...",
      "number": 3,
      "score": 4.2952,
      "section": "Changing a trip after booking",
      "source": "travel/trips-and-itineraries.md"
    },
    {
      "chunk": 4,
      "coverage": 0.333,
      "excerpt": "A budget belongs to one trip and records a total in AUD alongside the amount committed by current selections. The remaining budget is the total minus the committed amount, and it is allowed to go negative - the traveller is warned rather th...",
      "number": 4,
      "score": 4.1342,
      "section": "Budget",
      "source": "travel/flights-hotels-budget.md"
    }
  ],
  "confidence": "high",
  "confidence_reason": "best score 7.0355 with 67% question coverage, corroborated by 4 passages",
  "grounded": true,
  "model": "llama3.2:latest",
  "question": "How should I split a trip budget across days?"
}
```


### 2.5 Insufficient context (`/ask`)

Nothing clears the relevance floor, so no model call is made.

```console
$ curl -s localhost:5500/ask -H 'Content-Type: application/json' -d '{"question": "What is the boiling point of tungsten?"}'
```

```json
{
  "answer": "I don't have enough information in the NextStop knowledge base to answer that. Nothing in the indexed travel or project documentation is relevant to this question, so I would be guessing rather than answering.",
  "citations": [],
  "confidence": "insufficient",
  "confidence_reason": "no chunk scored above zero",
  "grounded": false,
  "model": null,
  "question": "What is the boiling point of tungsten?"
}
```


## 3. Through student-1's backend/API (the frontend's path)

The frontend posts these same form fields to `/api/student-1/ai/*`; nginx proxies them to student-1-api. The responses are the HTMX fragments the page renders.


### 3.1 MCP via student-1-api

```console
$ curl -s localhost:8081/api/student-1/ai/mcp -d tool=list_trips -d status=planned
```

```text
<div class='notice notice-ok'>Tool <strong>list_trips</strong> returned 5 row(s) from <strong>student-1-db</strong><span class='notice__meta'>called with status=planned</span></div><div class='table-wrap'><table><thead><tr><th>ID</th><th>Trip</th><th>Destination</th><th>Traveller</th><th>Start</th><th>End</th><th>Budget</th><th>Status</th></tr></thead><tbody><tr><td>2</td><td>Amalfi Coast Road Trip</td><td>Amalfi, Italy</td><td>Ben Nguyen</td><td>2026-06-10</td><td>2026-06-20</td><td>$6,800</td><td><span class='pill pill-planned'>planned</span></td></tr><tr><td>11</td><td>Norwegian Fjords</td><td>Bergen, Norway</td><td>Keiko Tanaka</td><td>2026-06-27</td><td>2026-07-06</td><td>$7,400</td><td><span class='pill pill-planned'>planned</span></td></tr><tr><td>9</td><td>Great Barrier Reef Dive</td><td>Cairns, Australia</td><td>Ines Fernandez</td><td>2026-09-05</td><td>2026-09-12</td><td>$3,100</td><td><span class='pill pill-planned'>planned</span></td></tr><tr><td>7</td><td>Marrakech and the Atlas</td><td>Marrakech, Morocco</td><td>Grace Liu</td><td>2026-10-14</td><td>2026-10-24</td><td>$5,200</td><td><span class='pill pill-planned'>planned</span></td></tr><tr><td>3</td><td>Patagonia Trekking</td><td>El Chalten, Argentina</td><td>Chiara Rossi</td><td>2026-11-02</td><td>2026-11-16</td><td>$9,100</td><td><span class='pill pill-planned'>planned</span></td></tr></tbody></table></div><details class='raw-result'><summary>Structured result (JSON)</summary><pre>{
  &quot;content&quot;: [
    {
      &quot;text&quot;: &quot;list_trips returned 5 row(s) from student-1-db&quot;,
      &quot;type&quot;: &quot;text&quot;
    }
  ],
  &quot;isError&quot;: false,
  &quot;structuredContent&quot;: {
    &quot;arguments&quot;: {
      &quot;status&quot;: &quot;planned&quot;
    },
    &quot;owner&quot;: &quot;student-1&quot;,
    &quot;row_count&quot;: 5,
    &quot;rows&quot;: [
      {
        &quot;budget_aud&quot;: 6800.0,
        &quot;destination&quot;: &quot;Amalfi, Italy&quot;,
        &quot;end_date&quot;: &quot;2026-06-20&quot;,
        &quot;start_date&quot;: &quot;2026-06-10&quot;,
        &quot;status&quot;: &quot;planned&quot;,
        &quot;traveller_id&quot;: 2,
        &quot;trip_id&quot;: 2,
        &quot;trip_name&quot;: &quot;Amalfi Coast Road Trip&quot;
      },
      {
        &quot;budget_aud&quot;: 7400.0,
        &quot;destination&quot;: &quot;Bergen, Norway&quot;,
        &quot;end_date&quot;: &quot;2026-07-06&quot;,
        &quot;start_date&quot;: &quot;2026-06-27&quot;,
        &quot;status&quot;: &quot;planned&quot;,
        &quot;traveller_id&quot;: 11,
        &quot;trip_id&quot;: 11,
        &quot;trip_name&quot;: &quot;Norwegian Fjords&quot;
      },
      {
        &quot;budget_aud&quot;: 3100.0,
        &quot;destination&quot;: &quot;Cairns, Australia&quot;,
        &quot;end_date&quot;: &quot;2026-09-12&quot;,
        &quot;start_date&quot;: &quot;2026-09-05&quot;,
... (31 more lines truncated)
```


### 3.2 MCP boundary refusal via student-1-api

`trip_id` must be at least 1; the backend forwards it and the MCP server refuses it at the `schema-checked` boundary. The frontend shows the refusal rather than hiding it.

```console
$ curl -s localhost:8081/api/student-1/ai/mcp -d tool=get_trip_itinerary -d trip_id=0
```

```text
<div class='notice notice-error'>MCP refused this call at the <strong>schema-checked</strong> boundary. Nothing was read from the database.</div><pre>argument &#x27;trip_id&#x27; must be &gt;= 1</pre><details class='raw-result'><summary>Structured result (JSON)</summary><pre>{
  &quot;boundary&quot;: &quot;schema-checked&quot;,
  &quot;content&quot;: [
    {
      &quot;text&quot;: &quot;argument &#x27;trip_id&#x27; must be &gt;= 1&quot;,
      &quot;type&quot;: &quot;text&quot;
    }
  ],
  &quot;isError&quot;: true
}</pre></details>
```


### 3.3 Grounded RAG answer via student-1-api

```console
$ curl -s localhost:8081/api/student-1/ai/rag --data-urlencode 'question=How should I split a trip budget across days?'
```

```text
<div class='chat-msg user'><div class='who'>You</div><div class='bubble'>How should I split a trip budget across days?</div></div><div class='chat-msg bot'><div class='who'>NextStop AI (grounded)</div><div class='bubble'>I can answer that based on [1]. According to the planning rule of thumb for a mid-range traveller, allocate roughly 40 per cent of a trip budget to flights, 30 per cent to accommodation, 20 per cent to food and activities, and keep 10 per cent as contingency.<div class='citations'><span class='pill pill-booked'>confidence: high</span><p class='muted'>best score 7.0355 with 67% question coverage, corroborated by 4 passages</p><strong>Sources</strong><ol class='citation-list'><li>[1] <code>travel/trips-and-itineraries.md</code> &rsaquo; Budget guidance <span class='muted'>(score 7.0355)</span></li><li>[2] <code>travel/trips-and-itineraries.md</code> &rsaquo; Itinerary days <span class='muted'>(score 6.4044)</span></li><li>[3] <code>travel/trips-and-itineraries.md</code> &rsaquo; Changing a trip after booking <span class='muted'>(score 4.2952)</span></li><li>[4] <code>travel/flights-hotels-budget.md</code> &rsaquo; Budget <span class='muted'>(score 4.1342)</span></li></ol></div></div></div>
```


### 3.4 Insufficient context via student-1-api

```console
$ curl -s localhost:8081/api/student-1/ai/rag --data-urlencode 'question=What is the boiling point of tungsten?'
```

```text
<div class='chat-msg user'><div class='who'>You</div><div class='bubble'>What is the boiling point of tungsten?</div></div><div class='chat-msg bot'><div class='who'>NextStop AI (grounded)</div><div class='bubble'>I don&#x27;t have enough information in the NextStop knowledge base to answer that. Nothing in the indexed travel or project documentation is relevant to this question, so I would be guessing rather than answering.<div class='citations'><span class='pill pill-cancelled'>insufficient context</span><p class='muted'>no chunk scored above zero</p></div></div></div>
```


### 3.5 Release 0 AI-Mode chatbot still answers

```console
$ curl -s localhost:8081/api/student-1/ai/chat --data-urlencode 'question=Which of the trips is the most expensive?'
```

```text
<div class='chat-msg user'><div class='who'>You</div><div class='bubble'>Which of the trips is the most expensive?</div></div><div class='chat-msg bot'><div class='who'>NextStop AI</div><div class='bubble'>The most expensive trip is #5 Iceland Ring Road to Reykjavik, Iceland, with a budget of AUD 8750.</div></div>
```


## 4. Release 0 functionality: student-1 CRUD smoke test

Frontend, backend/API and database all exercised.

```console
$ python3 scripts/smoke_test.py 1
```

```text
Smoke test: student-1
  ok  database service is healthy
  ok  backend/API service is healthy
  ok  GET /trips returns 200
  ok  GET /trips returns a list
  ok  /trips is seeded with at least 10 records (found 12)
  ok  POST /trips creates a record (201)
  ok  GET /trips/13 reads it back
  ok  PUT /trips/13 updates it
  ok  update actually changed status to booked
  ok  DELETE /trips/13 removes it
  ok  GET /trips/13 is 404 after delete
  ok  backend/API GET /trips returns 200
  ok  backend/API returns an HTML fragment, not JSON
  ok  frontend serves its page
  ok  page has HTMX attributes (7 found)
  ok  page calls its own API (/api/student-1/)
  ok  page uses the shared CSS theme
  ok  shared access API serves traveller records
  ok  shared access DB is seeded (12 travellers)
  ok  trip table resolves traveller names cross-service (e.g. ['Amara Okafor'])
  ok  no trip fell back to a raw traveller id

student-1 passed all checks.
```

```console
$ curl -s -o /dev/null -w 'frontend HTTP %{http_code}\n' localhost:8081
```

```text
frontend HTTP 200
```


## 5. Docker Compose deployment

AI-Mode, MCP, RAG and the loop are not compose services; the backend carries the connection configuration.

```console
$ docker compose config --services
```

```text
student-3-db
student-5-db
student-5-api
student-5-frontend
student-1-db
student-2-db
shared-db
shared-api
shared-frontend
student-1-api
student-2-api
mailpit
student-4-db
student-4-api
student-1-frontend
student-3-api
student-3-frontend
student-4-frontend
student-2-frontend
```

```console
$ docker exec student-1-api env | grep -E '^(AI_MODE|MCP|RAG)_' | sort
```

```text
AI_MODE_ENABLED=true
AI_MODE_URL=http://host.docker.internal:5300
MCP_ENABLED=true
MCP_SERVER_URL=http://host.docker.internal:5400
RAG_ENABLED=true
RAG_SERVER_URL=http://host.docker.internal:5500
```
