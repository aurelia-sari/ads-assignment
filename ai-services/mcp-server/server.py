"""Shared local MCP server for Group 25 (Release 1).

One non-containerised MCP server on the host, used by all five student
features. It is deliberately NOT a docker-compose service: the Release 1 brief
requires AI-Mode, MCP, RAG and the agentic loop to run locally, with the
containerised feature microservices reaching them over host.docker.internal.

Request flow:
    Frontend -> student-N-api -> MCP server -> student-N-db

Two surfaces are exposed over the same registry:

  POST /mcp     JSON-RPC 2.0, the MCP-shaped surface the backends call
                (initialize, tools/list, tools/call)
  GET  /health  plain health probe
  GET  /tools   plain tool listing, for terminal validation and the report

Run it with:  ./scripts/ai_services.sh up
"""

import os

from flask import Flask, jsonify, request
from flask_cors import CORS

import boundaries
import tools

app = Flask(__name__)
CORS(app)

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "group25-mcp", "version": "1.0.0"}


def _rpc_result(request_id, result):
    return jsonify({"jsonrpc": "2.0", "id": request_id, "result": result})


def _rpc_error(request_id, code, message, data=None):
    error = {"code": code, "message": message}
    if data:
        error["data"] = data
    return jsonify({"jsonrpc": "2.0", "id": request_id, "error": error})


@app.get("/health")
def health():
    return jsonify(
        {
            "service": "mcp-server",
            "status": "running",
            "containerised": False,
            "protocol_version": PROTOCOL_VERSION,
            "registered_tools": len(tools.REGISTRY),
        }
    )


@app.get("/tools")
def list_tools():
    """Plain listing, so the tool registry can be validated from a terminal."""
    return jsonify({"tools": tools.describe()})


@app.post("/mcp")
def mcp():
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if method == "initialize":
        return _rpc_result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        )

    if method == "tools/list":
        return _rpc_result(request_id, {"tools": tools.describe()})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = tools.call(name, arguments)
        except boundaries.BoundaryError as exc:
            # A refused call is a successful MCP response carrying an error
            # result, not a transport failure. The boundary that refused it is
            # named so the caller (and the agentic loop) can assert on it.
            return _rpc_result(
                request_id,
                {
                    "isError": True,
                    "boundary": exc.boundary,
                    "content": [{"type": "text", "text": str(exc)}],
                },
            )

        summary = (
            f"{result['tool']} returned {result['row_count']} row(s) "
            f"from {result['source']}"
            + (" (truncated)" if result["truncated"] else "")
        )
        return _rpc_result(
            request_id,
            {
                "isError": False,
                "content": [{"type": "text", "text": summary}],
                "structuredContent": result,
            },
        )

    return _rpc_error(request_id, -32601, f"unknown method: {method}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("MCP_PORT", "5400")))
