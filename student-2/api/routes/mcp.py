"""MCP routes for Student 2."""

import requests
from flask import Blueprint, jsonify, request

from services import mcp_client


mcp_bp = Blueprint("mcp", __name__)


# Validate text input
def _text(value, field, maximum, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > maximum:
        raise ValueError(f"{field} must be {maximum} characters or fewer")
    return value


# Search places
@mcp_bp.post("/mcp/search-places")
def search_places():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON request body is required."}), 400

    try:
        category = _text(payload.get("category"), "category", 40, required=True)
        name = _text(payload.get("name"), "name", 60)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        return jsonify(mcp_client.search_places(category, name)), 200
    except mcp_client.MCPDisabled as exc:
        return jsonify({"error": str(exc)}), 503
    except requests.Timeout:
        return jsonify({"error": "Shared MCP timed out."}), 504
    except requests.RequestException:
        return jsonify({"error": "Could not reach shared MCP."}), 503
    except mcp_client.MCPProtocolError as exc:
        return jsonify({"error": str(exc)}), 502
