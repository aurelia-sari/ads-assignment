import os

from flask import Blueprint, jsonify, request
from services import mcp_client

mcp_tools_bp = Blueprint("mcp_tools", __name__)

RELEVANT_TOOLS = {"search_flights", "search_hotels"}

MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() == "true"
DISABLED_MESSAGE = (
    "MCP is disabled in this deployment (cloud default). "
    "It runs in the local deployment, where the shared MCP server is available."
)


@mcp_tools_bp.get("/mcp/tools")
def list_tools():
    if not MCP_ENABLED:
        return jsonify({"disabled": True, "message": DISABLED_MESSAGE, "tools": []})
    try:
        tools = mcp_client.list_tools()
    except Exception as exc:
        return jsonify({"error": f"MCP server unreachable: {exc}"}), 503
    tools = [t for t in tools if t.get("name") in RELEVANT_TOOLS]
    return jsonify({"tools": tools})


@mcp_tools_bp.post("/mcp/call")
def call_tool():
    if not MCP_ENABLED:
        return jsonify({"ok": False, "error": DISABLED_MESSAGE, "boundary": "disabled"})
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
