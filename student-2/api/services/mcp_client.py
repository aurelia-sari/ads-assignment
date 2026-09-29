"""MCP client for Student 2."""

import os

import requests


MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://host.docker.internal:5400")
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() not in ("false", "0", "no")
TIMEOUT = float(os.getenv("MCP_TIMEOUT", "10"))


class MCPDisabled(Exception):
    pass


class MCPProtocolError(Exception):
    pass


# Search places
def search_places(category, name=None):
    """Search places through the shared MCP service."""
    if not MCP_ENABLED:
        raise MCPDisabled("MCP is disabled in this environment.")

    arguments = {"category": category}
    if name:
        arguments["name"] = name

    response = requests.post(
        f"{MCP_SERVER_URL}/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "student-2-search-places",
            "method": "tools/call",
            "params": {"name": "search_places", "arguments": arguments},
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    try:
        body = response.json()
        if "error" in body:
            raise MCPProtocolError(body["error"].get("message", "MCP request failed."))
        result = body["result"]
    except (KeyError, TypeError, ValueError) as exc:
        raise MCPProtocolError("Shared MCP returned an invalid response.") from exc

    if not isinstance(result, dict):
        raise MCPProtocolError("Shared MCP returned an invalid result.")

    if result.get("isError"):
        content = result.get("content") or []
        detail = content[0].get("text") if content and isinstance(content[0], dict) else None
        raise MCPProtocolError(detail or "The search_places tool failed.")

    if not isinstance(result.get("structuredContent"), dict):
        raise MCPProtocolError("Shared MCP response has no structured result.")

    return result
