"""Client for the shared MCP server (student-4, Aurelia Sari).

The server runs on the host, not in Docker, so the container reaches it through
host.docker.internal. CI sets MCP_ENABLED=false because nothing runs there.
"""

import os

import requests

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://host.docker.internal:5400")
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() not in ("false", "0", "no")

TIMEOUT = 30


class MCPDisabled(Exception):
    pass


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
        raise requests.RequestException(f"MCP error: {body['error'].get('message')}")
    return body["result"]


def call_tool(name, arguments=None):
    """Returns the full MCP result. A boundary refusal comes back with isError set, not as an exception."""
    return _rpc("tools/call", {"name": name, "arguments": arguments or {}})


def health():
    if not MCP_ENABLED:
        raise MCPDisabled("MCP is disabled in this environment (MCP_ENABLED=false)")
    response = requests.get(f"{MCP_SERVER_URL}/health", timeout=3)
    response.raise_for_status()
    return response.json()
