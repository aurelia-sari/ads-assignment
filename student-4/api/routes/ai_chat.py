"""AI assistant blueprint for Travel Guides (student-4, Aurelia Sari).

One session per (user, destination). Each question runs through
agentic_loop.core.orchestrator's Plan -> Act -> Observe -> Adapt loop.
"""

from flask import Blueprint, jsonify, request

from agentic_loop.collectors.guide_collector import collect_destination, collect_destinations
from agentic_loop.core.classifier import extract_destination
from agentic_loop.core.orchestrator import run as run_guide_chat_turn
from services import database_api
from services.shared_client import is_authenticated
from views.ai_formatter import (
    chat_turn_fragment,
    error_fragment,
    session_fragment,
    session_list_fragment,
)

ai_chat_bp = Blueprint("ai_chat", __name__)


def _wants_html():
    return bool(request.headers.get("HX-Request"))


def _error(status, message, detail=""):
    if _wants_html():
        return error_fragment(message, detail), status
    return jsonify({"error": message}), status


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _respond(session_id, question, result):
    if _wants_html():
        return chat_turn_fragment(session_id, question, result), 200
    return jsonify({"session_id": session_id, "question": question, **result}), 200


@ai_chat_bp.post("/ai/guide-chat")
def guide_chat():
    payload = request.get_json(silent=True) or request.form
    user_id = _to_int(payload.get("user_id"))
    question = (payload.get("question") or "").strip()
    session_id = _to_int(payload.get("session_id"))

    if not user_id:
        return _error(401, "Sign in to use the AI assistant.")
    if not is_authenticated(user_id):
        return _error(401, "Your session has expired. Sign in again.")
    if not question:
        return _error(400, "Ask a question first.")

    known_destination_id = None
    if session_id:
        session_response = database_api.get_chat_session(session_id)
        if session_response.status_code != 200:
            return _error(404, "This chat session could not be found.")
        known_destination_id = session_response.json()["destination_id"]

    matched_id = []

    def resolve_destination():
        matched = extract_destination(question, collect_destinations())
        if matched:
            matched_id.append(matched["id"])
            return matched
        return collect_destination(known_destination_id) if known_destination_id else None

    try:
        result = run_guide_chat_turn(question, resolve_destination)
    except Exception as exc:  # AI-Mode or student-4-db unreachable mid-turn
        return _error(503, "Could not reach the AI-Mode service.", exc)

    if session_id:
        if matched_id and matched_id[0] != known_destination_id:
            database_api.update_chat_session_destination(session_id, matched_id[0])
    elif matched_id:
        create_response = database_api.create_chat_session(user_id, matched_id[0])
        if create_response.status_code != 201:
            return _error(503, "Could not start a chat session.")
        session_id = create_response.json()["id"]
    else:
        return _respond(session_id, question, result)

    database_api.add_chat_message(session_id, "user", question)
    database_api.add_chat_message(session_id, "assistant", result["answer"], result["intent"])

    return _respond(session_id, question, result)


@ai_chat_bp.get("/ai/guide-chat/session/<int:session_id>")
def get_guide_chat_session(session_id):
    response = database_api.get_chat_session(session_id)
    if response.status_code == 404:
        return _error(404, "This chat session could not be found.")
    if response.status_code != 200:
        return _error(503, "Could not reach the Account & Dashboard database service.")

    session = response.json()

    if _wants_html():
        return session_fragment(session), 200

    return jsonify(session), 200


@ai_chat_bp.delete("/ai/guide-chat/session/<int:session_id>")
def delete_guide_chat_session(session_id):
    response = database_api.delete_chat_session(session_id)
    if response.status_code == 404:
        return _error(404, "This chat session could not be found.")
    if response.status_code != 200:
        return _error(503, "Could not reach the Account & Dashboard database service.")

    if _wants_html():
        return "", 200

    return jsonify({"deleted": True}), 200


@ai_chat_bp.get("/users/<int:user_id>/guide-chat-sessions")
def list_guide_chat_sessions(user_id):
    response = database_api.list_user_chat_sessions(user_id)
    if response.status_code != 200:
        return _error(503, "Could not reach the Account & Dashboard database service.")

    sessions = response.json()

    if _wants_html():
        return session_list_fragment(sessions), 200

    return jsonify(sessions), 200
