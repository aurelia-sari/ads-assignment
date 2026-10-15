"""Evidence sources the Planner can choose from, and the code that fetches them.

The Worker answers from evidence only, so where that evidence comes from has
to be explicit. A caller offers three kinds of source:

  supplied   data the feature's backend/API already holds and passes in,
             e.g. the trip row the traveller is looking at
  mcp:<tool> a call to a registered tool on the shared MCP server, with the
             arguments the backend chose. The MCP server still enforces its
             own boundaries, so a multi-agent workflow cannot read anything
             the feature could not read through MCP directly.
  rag        retrieval (not generation) from the shared RAG server's
             knowledge base, using the task as the query

The Planner sees the list as S1..Sn and picks which ones it needs. Only those
are fetched, and they reach the Worker renumbered as E1..En.
"""

import json
import os

import requests

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:5400")
RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://localhost:5500")

TIMEOUT = 30

# A small local model has a small context window. Evidence beyond this is cut
# rather than allowed to push the plan and instructions out of the prompt.
MAX_EVIDENCE_CHARS = int(os.getenv("MULTI_AGENT_MAX_EVIDENCE_CHARS", "2500"))


def _clip(text):
    if len(text) <= MAX_EVIDENCE_CHARS:
        return text
    return text[:MAX_EVIDENCE_CHARS] + "\n... (truncated)"


def candidate_sources(task, supplied=None, mcp_calls=None, use_rag=True):
    """Describe every source that could be fetched, without fetching any."""
    sources = []
    for item in supplied or []:
        sources.append(
            {
                "kind": "supplied",
                "label": str(item.get("label") or "supplied by the feature"),
                "content": str(item.get("content") or ""),
            }
        )
    for call in mcp_calls or []:
        tool = str(call.get("tool") or "")
        arguments = call.get("arguments") or {}
        sources.append(
            {
                "kind": "mcp",
                "label": f"MCP tool {tool}({json.dumps(arguments)})",
                "tool": tool,
                "arguments": arguments,
            }
        )
    if use_rag:
        sources.append(
            {
                "kind": "rag",
                "label": "NextStop knowledge base passages retrieved for the task",
                "query": task,
            }
        )
    for number, source in enumerate(sources, start=1):
        source["id"] = f"S{number}"
    return sources


def _fetch_mcp(source):
    response = requests.post(
        f"{MCP_SERVER_URL}/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": source["tool"], "arguments": source["arguments"]},
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        return False, f"MCP error: {body['error'].get('message')}"

    result = body["result"]
    if result.get("isError"):
        # A boundary refusal is still evidence: the Worker should say the data
        # was refused, not quietly answer without it.
        text = result["content"][0]["text"]
        return False, f"refused at the {result.get('boundary')} boundary: {text}"

    structured = result["structuredContent"]
    return True, _clip(json.dumps(structured["rows"], indent=1, default=str))


def _fetch_rag(source):
    response = requests.post(
        f"{RAG_SERVER_URL}/search",
        json={"question": source["query"], "top_k": 3},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("confidence") == "insufficient":
        return False, (
            "the knowledge base has nothing relevant to this task "
            f"({body.get('confidence_reason')})"
        )
    passages = [
        f"({hit['source']} > {hit['section']}) {hit['excerpt']}" for hit in body["hits"]
    ]
    return True, _clip("\n".join(passages))


def gather(sources, selected_ids):
    """Fetch the selected sources. A source that fails is recorded, not dropped."""
    evidence = []
    for source in sources:
        if source["id"] not in selected_ids:
            continue
        try:
            if source["kind"] == "supplied":
                ok, content = True, _clip(source["content"])
            elif source["kind"] == "mcp":
                ok, content = _fetch_mcp(source)
            else:
                ok, content = _fetch_rag(source)
        except requests.RequestException as exc:
            ok, content = False, f"{source['kind']} source unavailable: {exc}"

        evidence.append(
            {
                "id": f"E{len(evidence) + 1}",
                "source_id": source["id"],
                "kind": source["kind"],
                "label": source["label"],
                "ok": ok,
                "content": content,
            }
        )
    return evidence


def render(evidence):
    """Evidence as the Worker and Reviewer see it."""
    if not evidence:
        return "(no evidence was gathered)"
    blocks = []
    for item in evidence:
        status = "" if item["ok"] else " [NOT AVAILABLE]"
        blocks.append(f"[{item['id']}] {item['label']}{status}\n{item['content']}")
    return "\n\n".join(blocks)
