"""Student 5 - Aung Ko Khaing
Client for the shared MCP server (Release 1).
"""

import os
import uuid

import requests

MCP_URL = os.getenv("MCP_URL", "http://host.docker.internal:5400")
TIMEOUT = 10


class McpError(Exception):
    """Raised when the MCP server cannot be reached or refuses a call.

    `.boundary` is set when the server refused the call (e.g. a disallowed
    target or a failed schema check), matching the `boundary` field
    boundaries.BoundaryError attaches on the server side.
    """

    def __init__(self, message, boundary=None):
        super().__init__(message)
        self.boundary = boundary


def call_tool(name, arguments=None):
    """Call one registered MCP tool via JSON-RPC 2.0 tools/call.

    Returns the tool's structuredContent (a dict with at least "rows").
    Raises McpError on any transport failure or refusal - callers that treat
    MCP context as "nice to have, not required" should catch McpError
    specifically and fall back to an ungrounded answer, the same way the
    rest of this codebase degrades gracefully when an optional upstream is
    unreachable.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }

    try:
        response = requests.post(f"{MCP_URL}/mcp", json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        body = response.json()
    except requests.RequestException as exc:
        raise McpError(f"MCP server unreachable at {MCP_URL}: {exc}") from exc
    except ValueError as exc:
        raise McpError(f"MCP server returned a non-JSON response: {exc}") from exc

    if "error" in body:
        raise McpError(body["error"].get("message", "MCP call failed"))

    result = body.get("result", {})
    if result.get("isError"):
        content = result.get("content") or [{}]
        raise McpError(
            content[0].get("text", "tool call refused by the MCP server"),
            boundary=result.get("boundary"),
        )

    return result.get("structuredContent", {})


def list_tools():
    """Plain GET /tools listing - useful for a diagnostics page or a demo."""
    response = requests.get(f"{MCP_URL}/tools", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json().get("tools", [])


def health():
    response = requests.get(f"{MCP_URL}/health", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


# --- Cross-feature lookups used to enrich the Bookings & Budget chatbot ----
# Each of these wraps one tool that is already registered for ANOTHER
# student's feature in the shared tools.py. student-5's own data (flights,
# hotels, budgets, selections, search history) keeps going through
# services/database_api.py as before - MCP is only for data this feature
# does not own.

def lookup_destination_guide(query):
    """student-4's destination-guide lookup, by city or country name.

    Useful when a traveller asks the chatbot something like "what's
    Melbourne like" alongside a flight/hotel question.
    """
    try:
        result = call_tool("lookup_destination_guide", {"query": query})
    except McpError:
        return []
    return result.get("rows", [])


def search_places(name=None, category=None):
    """student-2's attractions/places search, filtered client-side by the
    MCP tool itself (that tool's backing API has no query params of its
    own, so tools.py already does the filtering server-side)."""
    arguments = {}
    if name:
        arguments["name"] = name
    if category:
        arguments["category"] = category
    try:
        result = call_tool("search_places", arguments)
    except McpError:
        return []
    return result.get("rows", [])


def list_trips(destination=None, status=None):
    """student-1's trip list, e.g. to check whether the traveller already
    has a planned trip to the destination they are searching flights for."""
    arguments = {}
    if destination:
        arguments["destination"] = destination
    if status:
        arguments["status"] = status
    try:
        result = call_tool("list_trips", arguments)
    except McpError:
        return []
    return result.get("rows", [])

def search_flights(destination=None, origin=None, budget_aud=None):

    arguments = {}
    if destination:
        arguments["destination"] = destination
    if origin:
        arguments["origin"] = origin
    if budget_aud is not None:
        arguments["budget_aud"] = budget_aud
    try:
        result = call_tool("search_flights", arguments)
    except McpError:
        return []
    return result.get("rows", [])