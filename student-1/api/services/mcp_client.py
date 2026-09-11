"""Client for the shared MCP server.

student-1-api does not implement tools of its own. It calls the one shared MCP
server that every feature uses, over JSON-RPC, and renders whatever structured
result comes back.

The server is not containerised, so in Docker it is reached through
host.docker.internal. In CI it is not running at all, which is what
MCP_ENABLED=false is for: the integration stays in the image and the runtime
path is skipped, rather than waiting out a timeout against nothing.
"""

import os

import requests

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://host.docker.internal:5400")
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() not in ("false", "0", "no")

TIMEOUT = 30


class MCPDisabled(Exception):
    """Raised when MCP is switched off for this environment, as it is in CI."""


def _rpc(method, params=None):
    if not MCP_ENABLED:
        raise MCPDisabled("MCP is disabled in this environment (MCP_ENABLED=false)")

    response = requests.post(
        f"{MCP_SERVER_URL}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()

    if "error" in body:
        raise requests.HTTPError(f"MCP error: {body['error'].get('message')}")

    return body["result"]


def list_tools():
    return _rpc("tools/list").get("tools", [])


def call_tool(name, arguments=None):
    """Call one registered tool.

    Returns the full MCP result, including the isError case, because a call
    refused at a tool boundary is a legitimate outcome the frontend should
    show rather than an exception to swallow.
    """
    return _rpc("tools/call", {"name": name, "arguments": arguments or {}})
