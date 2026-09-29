"""RAG routes for Student 2."""

import requests
from flask import Blueprint, jsonify, request

from services import rag_client


rag_bp = Blueprint("rag", __name__)


# Validate a query or question
def _question(field):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("A JSON request body is required.")
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    value = value.strip()
    if len(value) > 500:
        raise ValueError(f"{field} must be 500 characters or fewer")
    return value


# Call shared RAG safely
def _call_shared(operation):
    try:
        return jsonify(operation()), 200
    except rag_client.RAGDisabled as exc:
        return jsonify({"error": str(exc)}), 503
    except requests.Timeout:
        return jsonify({"error": "Shared RAG timed out."}), 504
    except requests.RequestException:
        return jsonify({"error": "Could not reach shared RAG."}), 503
    except rag_client.RAGUpstreamError as exc:
        return jsonify(exc.payload), exc.status_code
    except rag_client.RAGProtocolError as exc:
        return jsonify({"error": str(exc)}), 502


# Refresh knowledge
@rag_bp.post("/rag/reindex")
def reindex():
    return _call_shared(rag_client.reindex)


# Retrieve context
@rag_bp.post("/rag/search")
def search():
    try:
        question = _question("query")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return _call_shared(lambda: rag_client.search(question))


# Ask with citations
@rag_bp.post("/rag/ask")
def ask():
    try:
        question = _question("question")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return _call_shared(lambda: rag_client.ask(question))
