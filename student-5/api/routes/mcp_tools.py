"""Student 5 - Aung Ko Khaing
Manual MCP tool runner for Bookings & Budget.

Separate from the AI assistant chat (routes/ai_chat.py), which calls MCP
tools automatically while building grounding context for an LLM answer.
This route lets a person pick a registered tool, fill in its arguments by
hand, and see the raw structured result - no model involved at all - which
is the clean way to demonstrate the MCP boundary layer itself (schema
validation, read-only enforcement, allowlisted targets) rather than an
LLM-generated answer that happens to have used a tool.
"""

from flask import Blueprint, jsonify, request

from services import mcp_client

mcp_tools_bp = Blueprint("mcp_tools", __name__)

# Tools relevant to demoing this feature: student-5's own tool plus the
# cross-feature ones ai_chat.py already calls. Keeps the picker from being
# cluttered with every other student's tools (student-1's get_trip_itinerary,
# student-3's find_travel_mates, etc.) that this feature has no reason to
# call from its own UI.
RELEVANT_TOOLS = {"search_flights", "lookup_destination_guide", "search_places", "list_trips"}


@mcp_tools_bp.get("/mcp/tools")
def list_tools():
    """Plain listing, filtered to the tools this feature's UI exposes."""
    try:
        tools = mcp_client.list_tools()
    except Exception as exc:
        return jsonify({"error": f"MCP server unreachable: {exc}"}), 503

    tools = [t for t in tools if t.get("name") in RELEVANT_TOOLS]
    return jsonify({"tools": tools})


@mcp_tools_bp.post("/mcp/call")
def call_tool():
    """Run one MCP tool with person-supplied arguments and return the raw
    structured result (or the boundary refusal, if the server refused it).

    A refusal (bad schema, disallowed target, unreachable upstream) is not
    an error in THIS route - it's exactly what boundaries.py is supposed to
    produce, so it comes back as a normal 200 with ok: false and the
    boundary name, for the frontend to render as a visible refusal rather
    than a generic failure.
    """
    payload = request.get_json(silent=True) or {}
    name = (payload.get("tool") or "").strip()
    arguments = payload.get("arguments") or {}

    if not name:
        return jsonify({"error": "tool name is required"}), 400
    if name not in RELEVANT_TOOLS:
        return jsonify({"error": f"'{name}' is not one of this feature's exposed tools"}), 400

    try:
        result = mcp_client.call_tool(name, arguments)
        return jsonify({"ok": True, "result": result})
    except mcp_client.McpError as exc:
        return jsonify({"ok": False, "error": str(exc), "boundary": exc.boundary})