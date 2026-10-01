"""Client for the shared local MCP server (student-3, Tanishpreet Kour)."""

import itertools
import os

import requests

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:5400")
TIMEOUT = 30
_ids = itertools.count(1)


def call_tool(tool_name, arguments):
    """Call one registered MCP tool and return its structured result.
    A boundary refusal comes back as a result with isError=True, not an exception."""
    payload = {
        "jsonrpc": "2.0",
        "id": next(_ids),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    r = requests.post(f"{MCP_SERVER_URL}/mcp", json=payload, timeout=30)
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise ValueError(body["error"].get("message", "MCP server error"))
    return body["result"]


def health():
    """Return the MCP server's /health JSON."""
    r = requests.get(f"{MCP_SERVER_URL}/health", timeout=3)
    r.raise_for_status()
    return r.json()