"""MCP and RAG routes - student-1's Release 1 extension.

The frontend never talks to the shared MCP or RAG servers directly. It calls
these two endpoints on student-1-api, which is what the Release 1 requirement
"through its backend/API" means in practice:

    Frontend -> student-1-api -> shared MCP server -> student-1-db
    Frontend -> student-1-api -> shared RAG server -> AI-Mode -> Ollama
"""

import requests
from flask import Blueprint, request

from services import database_api, mcp_client, rag_client
from views.formatters import (
    ai_disabled_fragment,
    error_fragment,
    mcp_result,
    rag_answer,
)

ai_tools_bp = Blueprint("ai_tools", __name__)


@ai_tools_bp.post("/ai/mcp")
def mcp_call():
    """Invoke one registered tool on the shared MCP server."""
    tool = request.form.get("tool", "").strip()
    destination = request.form.get("destination", "").strip()
    status = request.form.get("status", "").strip()
    trip_id = request.form.get("trip_id", "").strip()

    if not tool:
        return error_fragment("Choose a tool to run."), 400

    # Only send arguments the chosen tool actually declares. Sending an empty
    # field would be rejected by the server's schema boundary, which is correct
    # behaviour but a confusing thing to show someone who left a box blank.
    arguments = {}
    if tool == "list_trips":
        if destination:
            arguments["destination"] = destination
        if status:
            arguments["status"] = status
    elif tool == "get_trip_itinerary":
        if not trip_id.isdigit():
            return error_fragment("get_trip_itinerary needs a numeric trip id."), 400
        arguments["trip_id"] = int(trip_id)

    try:
        result = mcp_client.call_tool(tool, arguments)
    except mcp_client.MCPDisabled:
        return ai_disabled_fragment("MCP"), 200
    except requests.RequestException as exc:
        return error_fragment(
            "Could not reach the shared MCP server.",
            f"{exc}\n\nIt is not containerised - start it with "
            "./scripts/ai_services.sh up",
        ), 503

    return mcp_result(tool, result), 200


@ai_tools_bp.post("/ai/rag")
def rag_ask():
    """Ask the shared RAG server a grounded question about trip planning."""
    question = request.form.get("question", "").strip()
    trip_id = request.form.get("trip_id", "").strip()

    if not question:
        return error_fragment("Ask a question first."), 400

    # A trip id lets the traveller ask "is my budget split sensible?" about a
    # real trip. It is passed as live context, never as a citable source.
    context = ""
    if trip_id.isdigit():
        try:
            response = database_api.get_trip(int(trip_id))
            if response.status_code == 200:
                trip = response.json()
                context = (
                    f"Trip {trip['trip_id']}: {trip['trip_name']} to "
                    f"{trip['destination']}, {trip['start_date']} to "
                    f"{trip['end_date']}, budget AUD {trip['budget_aud']:.0f}, "
                    f"status {trip['status']}."
                )
        except requests.RequestException:
            # The question is still answerable from the knowledge base alone.
            context = ""

    try:
        result = rag_client.ask(question, context=context)
    except rag_client.RAGDisabled:
        return ai_disabled_fragment("RAG"), 200
    except requests.RequestException as exc:
        return error_fragment(
            "Could not reach the shared RAG server.",
            f"{exc}\n\nIt is not containerised - start it with "
            "./scripts/ai_services.sh up",
        ), 503

    return rag_answer(question, result), 200
