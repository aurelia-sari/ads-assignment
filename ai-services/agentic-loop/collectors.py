"""ACT step: collect real evidence from the running application and the repo.

Nothing here asks the LLM anything. These functions make live HTTP calls and
read files, so that the OBSERVE step reviews facts rather than assumptions.

The loop runs on the host in Release 1, not in a container, so every service is
reached on a published localhost port rather than by compose DNS name.
"""

import json
import os
from pathlib import Path

import requests
import yaml

# ai-services/agentic-loop/collectors.py -> the repo root is three levels up.
REPO_ROOT = Path(os.getenv("REPO_ROOT", Path(__file__).resolve().parents[2]))

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://localhost:5300")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:5400")
RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://localhost:5500")
SHARED_API_URL = os.getenv("SHARED_API_URL", "http://localhost:5000")

# The scaffold /records endpoints are gone - every student now has a real
# schema, so the loop checks the resources those schemas actually expose.
STUDENTS = [
    ("student-1", "Trips & Itinerary",     5101, 5201, ["/trips", "/days"]),
    ("student-2", "Attractions & Dining",  5102, 5202, ["/places", "/recommendations"]),
    ("student-3", "Travel Mate",           5103, 5203, ["/trip_posts", "/connect_requests"]),
    ("student-4", "Account & Dashboard",   5104, 5204, ["/destinations"]),
    ("student-5", "Bookings & Budget",     5105, 5205, ["/flights/search", "/hotels/search"]),
]


def _get(url, timeout=4):
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code, response
    except requests.RequestException as exc:
        return None, str(exc)


def _read(relative_path):
    path = REPO_ROOT / relative_path
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def collect_database_evidence():
    lines = []
    for name, feature, _api_port, db_port, resources in STUDENTS:
        base = f"http://localhost:{db_port}"
        status, response = _get(f"{base}/health")
        if status != 200:
            lines.append(f"{name}-db: UNREACHABLE ({response})")
            continue

        lines.append(f"{name}-db: health 200 ({feature})")
        for resource in resources:
            status, response = _get(f"{base}{resource}")
            if status != 200:
                lines.append(f"  GET {resource}: status {status}")
                continue
            try:
                rows = response.json()
                count = len(rows) if isinstance(rows, list) else "n/a"
                sample = json.dumps(rows[0], sort_keys=True) if isinstance(rows, list) and rows else "{}"
                lines.append(f"  GET {resource}: 200, {count} rows, columns={sample[:180]}")
            except ValueError:
                lines.append(f"  GET {resource}: 200 but response was not JSON")
    return "\n".join(lines)


def collect_implementation_evidence():
    lines = []
    for name, feature, api_port, _db_port, _resources in STUDENTS:
        status, response = _get(f"http://localhost:{api_port}/health")
        state = "200" if status == 200 else f"{status or 'unreachable'} ({response if status is None else ''})"
        lines.append(f"{name}-api ({feature}): health {state}")

    status, response = _get(f"{AI_MODE_URL}/health")
    lines.append(f"ai-mode: health {status or 'unreachable'}")
    if status == 200:
        lines.append(f"  configured model: {response.json().get('model')}")

    status, response = _get(f"{AI_MODE_URL}/model", timeout=90)
    if status == 200:
        lines.append("  LLM reachable: yes")
    else:
        detail = response if isinstance(response, str) else response.text[:160]
        lines.append(f"  LLM reachable: NO -> {detail}")

    return "\n".join(lines)


def collect_architecture_evidence():
    compose = _read("docker-compose.yml") or ""
    nginx = _read("shared/nginx.conf") or ""

    parsed = yaml.safe_load(compose) if compose else {}
    services = parsed.get("services", {})
    profiled = {
        name for name, spec in services.items()
        if isinstance(spec, dict) and spec.get("profiles")
    }
    default_services = [name for name in services if name not in profiled]

    routed = [line.strip() for line in nginx.splitlines() if "proxy_pass" in line]

    status, response = _get(f"{SHARED_API_URL}/health/all", timeout=30)
    health_fragment = response.text[:400] if status == 200 else f"shared-api unreachable ({status})"

    return (
        f"docker-compose.yml declares {len(services)} services, "
        f"{len(default_services)} of which start by default "
        f"(profile-gated: {', '.join(sorted(profiled)) or 'none'}):\n"
        + "\n".join(f"  - {name}" for name in services)
        + f"\n\nshared/nginx.conf declares {len(routed)} proxy routes:\n"
        + "\n".join(f"  {route}" for route in routed)
        + f"\n\nLive health fragment from shared-api:\n{health_fragment}"
    )


def collect_devops_evidence():
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    if not workflow_dir.exists():
        return "No .github/workflows directory found."

    lines = []
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        steps = text.count("      - name:")
        # The workflows build through compose, so count both spellings.
        builds = text.count("docker compose build") + text.count("docker build")
        lines.append(
            f"{path.name}: {len(text.splitlines())} lines, "
            f"{builds} compose-build step(s), {steps} named step(s), triggers on "
            f"{'pull_request' if 'pull_request' in text else 'push only'}"
        )

    compose = _read("docker-compose.yml") or ""
    lines.append(f"docker-compose.yml present: {bool(compose)} ({len(compose.splitlines())} lines)")
    return "\n".join(lines)



def _post(url, payload, timeout=180):
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        return response.status_code, response
    except requests.RequestException as exc:
        return None, str(exc)


def _rpc(method, params=None):
    """One JSON-RPC call to the shared MCP server."""
    status, response = _post(
        f"{MCP_SERVER_URL}/mcp",
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        timeout=30,
    )
    if status != 200:
        return None, f"HTTP {status or 'unreachable'} ({response if status is None else ''})"
    try:
        body = response.json()
    except ValueError:
        return None, "response was not JSON"
    if "error" in body:
        return None, f"JSON-RPC error: {body['error']}"
    return body.get("result"), None


def collect_mcp_evidence():
    """MCP validation mode.

    Checks three things the brief asks for by name: that the server runs and is
    not containerised, that it exposes registered tools which return valid
    structured results, and that its declared tool boundaries actually refuse a
    call that crosses them. The last one matters most - a boundary that is
    documented but not enforced is worse than no boundary, because it is
    believed.
    """
    lines = []

    status, response = _get(f"{MCP_SERVER_URL}/health")
    if status != 200:
        return (
            f"MCP server UNREACHABLE at {MCP_SERVER_URL} ({response}).\n"
            "Start it with ./scripts/ai_services.sh up"
        )

    health = response.json()
    lines.append(
        f"MCP server: health 200, protocol {health.get('protocol_version')}, "
        f"{health.get('registered_tools')} registered tool(s), "
        f"containerised={health.get('containerised')}"
    )

    result, error = _rpc("tools/list")
    if error:
        return "\n".join(lines + [f"tools/list failed: {error}"])

    tools = result.get("tools", [])
    lines.append(f"\nRegistered tools ({len(tools)}):")
    for tool in tools:
        required = tool["inputSchema"].get("required") or []
        lines.append(
            f"  {tool['name']} (owner {tool['owner']}) -> {tool['target']}, "
            f"required args: {required or 'none'}, row limit {tool['rowLimit']}"
        )

    # --- valid calls: every registered tool must return a structured result ---
    lines.append("\nValid tool calls, one per registered tool:")
    probes = {
        "list_trips": {},
        "get_trip_itinerary": {"trip_id": 1},
        "search_places": {},
        "find_travel_mates": {},
        "lookup_destination_guide": {"query": "melbourne"},
        "search_flights": {},
    }
    for tool in tools:
        name = tool["name"]
        result, error = _rpc("tools/call", {"name": name, "arguments": probes.get(name, {})})
        if error:
            lines.append(f"  {name}: CALL FAILED - {error}")
            continue
        if result.get("isError"):
            lines.append(
                f"  {name}: refused at the '{result.get('boundary')}' boundary - "
                f"{result['content'][0]['text']}"
            )
            continue
        structured = result.get("structuredContent", {})
        lines.append(
            f"  {name}: OK, {structured.get('row_count')} row(s) from "
            f"{structured.get('source')}, truncated={structured.get('truncated')}"
        )

    # --- boundary probes: each MUST be refused, and name the right boundary ---
    lines.append("\nBoundary probes (each of these must be REFUSED):")
    probes = [
        ("unregistered tool", "drop_all_trips", {}, "registered"),
        ("unexpected argument", "list_trips", {"sql": "DROP TABLE trips"}, "schema-checked"),
        ("missing required argument", "get_trip_itinerary", {}, "schema-checked"),
        ("wrong argument type", "get_trip_itinerary", {"trip_id": "abc"}, "schema-checked"),
        ("value outside declared enum", "list_trips", {"status": "deleted"}, "schema-checked"),
        ("integer above declared maximum", "search_flights", {"budget_aud": 10 ** 9}, "schema-checked"),
    ]
    for label, name, arguments, expected in probes:
        result, error = _rpc("tools/call", {"name": name, "arguments": arguments})
        if error:
            lines.append(f"  {label}: INCONCLUSIVE - {error}")
        elif not result.get("isError"):
            lines.append(f"  {label}: NOT REFUSED - the boundary did not hold")
        elif result.get("boundary") != expected:
            lines.append(
                f"  {label}: refused, but at the '{result.get('boundary')}' boundary "
                f"rather than the expected '{expected}'"
            )
        else:
            lines.append(f"  {label}: refused at '{expected}' - {result['content'][0]['text']}")

    return "\n".join(lines)


def collect_rag_evidence():
    """RAG validation mode.

    Checks retrieval and grounding separately, because they fail separately. A
    grounded-looking answer over irrelevant passages and an insufficient-context
    response to a question the corpus does answer are both failures, and neither
    shows up if you only look at whether an answer came back.
    """
    lines = []

    status, response = _get(f"{RAG_SERVER_URL}/health")
    if status != 200:
        return (
            f"RAG server UNREACHABLE at {RAG_SERVER_URL} ({response}).\n"
            "Start it with ./scripts/ai_services.sh up"
        )

    health = response.json()
    lines.append(
        f"RAG server: health 200, {health.get('retrieval')} retrieval over "
        f"{health.get('chunks')} chunk(s) from {health.get('source_count')} source(s), "
        f"vocabulary {health.get('vocabulary')}, containerised={health.get('containerised')}"
    )
    lines.append("Indexed sources: " + ", ".join(health.get("sources", [])))

    # --- retrieval only: does the corpus surface the right file? ------------
    lines.append("\nRetrieval checks (question -> top source, score, confidence):")
    retrieval_probes = [
        ("How should I split my trip budget between flights and accommodation?",
         "travel/trips-and-itineraries.md"),
        ("Can I send a connect request to my own trip post?",
         "travel/travel-mate-matching.md"),
        ("Are hotel rates per person or per room?",
         "travel/flights-hotels-budget.md"),
        ("What does the price range mean for a restaurant?",
         "travel/attractions-and-dining.md"),
        ("What are the password requirements for an account?",
         "travel/accounts-and-guides.md"),
    ]
    for question, expected_source in retrieval_probes:
        status, response = _post(f"{RAG_SERVER_URL}/search", {"question": question}, timeout=20)
        if status != 200:
            lines.append(f"  {question[:52]}...: SEARCH FAILED ({response})")
            continue
        body = response.json()
        hits = body.get("hits", [])
        if not hits:
            lines.append(f"  {question[:52]}...: no hits, confidence {body.get('confidence')}")
            continue
        top = hits[0]
        verdict = "expected source" if top["source"] == expected_source else (
            f"UNEXPECTED - wanted {expected_source}"
        )
        lines.append(
            f"  {question[:52]}...: {top['source']} > {top['section']}, "
            f"score {top['score']}, confidence {body.get('confidence')} [{verdict}]"
        )

    # --- grounding: answer, citations and confidence together ---------------
    lines.append("\nGrounded answers (must carry citations and a confidence category):")
    for question, _ in retrieval_probes[:2]:
        status, response = _post(f"{RAG_SERVER_URL}/ask", {"question": question})
        if status != 200:
            body = response.json() if hasattr(response, "json") else {}
            lines.append(f"  {question[:52]}...: ASK FAILED - {body.get('detail', response)}")
            continue
        body = response.json()
        citations = body.get("citations", [])
        lines.append(f"  Q: {question}")
        lines.append(f"    grounded={body.get('grounded')} confidence={body.get('confidence')}")
        lines.append(f"    reason: {body.get('confidence_reason')}")
        lines.append(f"    answer: {body.get('answer', '')[:300]}")
        lines.append(
            "    citations: "
            + (", ".join(f"[{c['number']}] {c['source']}" for c in citations) or "NONE - ungrounded")
        )

    # --- the refusal path: a question the corpus cannot answer --------------
    lines.append("\nInsufficient-context checks (each MUST refuse rather than answer):")
    for question in [
        "What is the capital of Peru?",
        "How do I replace the brake pads on a 2012 Subaru?",
    ]:
        status, response = _post(f"{RAG_SERVER_URL}/ask", {"question": question})
        if status != 200:
            lines.append(f"  {question}: ASK FAILED ({status})")
            continue
        body = response.json()
        if body.get("grounded") or body.get("confidence") != "insufficient":
            lines.append(
                f"  {question}: NOT REFUSED - answered with confidence "
                f"{body.get('confidence')}. This is a grounding failure."
            )
        else:
            lines.append(f"  {question}: correctly refused ({body.get('confidence_reason')})")

    return "\n".join(lines)


COLLECTORS = {
    "db": ("the database microservices", "review/database_review_prompt.txt", collect_database_evidence),
    "implementation": ("the backend/API implementation", "review/implementation_review_prompt.txt", collect_implementation_evidence),
    "architecture": ("the microservices architecture", "review/architecture_review_prompt.txt", collect_architecture_evidence),
    "devops": ("the DevOps pipeline", "review/devops_review_prompt.txt", collect_devops_evidence),
    # Release 1 validation modes.
    "mcp": ("the shared MCP server", "review/mcp_review_prompt.txt", collect_mcp_evidence),
    "rag": ("the shared RAG server and its grounded responses", "review/rag_review_prompt.txt", collect_rag_evidence),
}
