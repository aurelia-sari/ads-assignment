"""Release 1 MCP and RAG proxy endpoints (student-4, Aurelia Sari).

The frontend never calls the shared servers directly. Every call goes through
these routes, which degrade to a clear disabled or unavailable response.

HTMX does not swap 4xx or 5xx responses by default, so HTMX callers always get
a 200 fragment. JSON callers get the real status code.
"""

import requests
from flask import Blueprint, jsonify, request

from services import mcp_client, rag_client
from views.ai_tools_formatter import (
    disabled_fragment,
    mcp_result_fragment,
    notice,
    rag_answer_fragment,
    status_fragment,
    unavailable_fragment,
)

ai_tools_bp = Blueprint("ai_tools", __name__)

MCP_TOOL = "lookup_destination_guide"
MAX_QUESTION_LENGTH = 500


def _wants_html():
    return bool(request.headers.get("HX-Request"))


def _reply(fragment, payload, status):
    if _wants_html():
        return fragment, 200
    return jsonify(payload), status


def _payload():
    return request.get_json(silent=True) or request.form


@ai_tools_bp.get("/ai-tools/status")
def ai_tools_status():
    status = {}
    for name, client, disabled in (
        ("mcp", mcp_client, mcp_client.MCPDisabled),
        ("rag", rag_client, rag_client.RAGDisabled),
    ):
        try:
            client.health()
            status[name] = "available"
        except disabled:
            status[name] = "disabled"
        except (requests.RequestException, ValueError):
            status[name] = "unavailable"

    return _reply(status_fragment(status), status, 200)


@ai_tools_bp.post("/mcp/destination-guide")
def mcp_destination_guide():
    # The query is forwarded as typed, so an empty or oversized one shows the MCP schema boundary refusing it.
    query = (_payload().get("query") or "").strip()

    try:
        result = mcp_client.call_tool(MCP_TOOL, {"query": query})
    except mcp_client.MCPDisabled as exc:
        return _reply(
            disabled_fragment("MCP", "MCP_ENABLED"),
            {"status": "disabled", "service": "mcp", "detail": str(exc)},
            200,
        )
    except (requests.RequestException, ValueError, KeyError) as exc:
        return _reply(
            unavailable_fragment("MCP"),
            {"status": "unavailable", "service": "mcp", "detail": str(exc)[:300]},
            503,
        )

    return _reply(mcp_result_fragment(MCP_TOOL, result), {"status": "ok", "tool": MCP_TOOL, "result": result}, 200)


@ai_tools_bp.post("/rag/ask")
def rag_ask():
    question = (_payload().get("question") or "").strip()

    if not question:
        return _reply(notice("Ask a question first."), {"error": "question is required"}, 400)
    if len(question) > MAX_QUESTION_LENGTH:
        message = f"Questions are limited to {MAX_QUESTION_LENGTH} characters."
        return _reply(notice(message), {"error": message}, 400)

    try:
        result = rag_client.ask(question)
    except rag_client.RAGDisabled as exc:
        return _reply(
            disabled_fragment("RAG", "RAG_ENABLED"),
            {"status": "disabled", "service": "rag", "detail": str(exc)},
            200,
        )
    except requests.HTTPError as exc:
        # The RAG server answers 503 with a hint when retrieval worked but AI-Mode did not.
        try:
            hint = exc.response.json().get("hint", "")
        except ValueError:
            hint = ""
        return _reply(
            unavailable_fragment("RAG", hint),
            {"status": "unavailable", "service": "rag", "detail": hint or str(exc)[:300]},
            503,
        )
    except (requests.RequestException, ValueError) as exc:
        return _reply(
            unavailable_fragment("RAG"),
            {"status": "unavailable", "service": "rag", "detail": str(exc)[:300]},
            503,
        )

    return _reply(rag_answer_fragment(question, result), {"status": "ok", **result}, 200)
