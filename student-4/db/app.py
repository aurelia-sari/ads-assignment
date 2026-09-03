"""Account & Dashboard database API (student-4, Aurelia Sari).

This service exclusively owns student4.db. Other backend/API microservices
must call these endpoints and must not open the SQLite file directly.

User accounts and access logs live in shared-db instead (see
shared/db/app.py), since a user's id and sign-in state are cross-cutting
data every feature may need. This service owns the Travel Guides.
"""

import sqlite3
from datetime import datetime, timezone

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_NAME = "/app/data/student4.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

@app.get("/health")
def health():
    get_db_connection().close()
    return jsonify({"service": "student-4-db", "status": "running"})

@app.get("/destinations")
def list_destinations():
    query = (request.args.get("query") or "").strip().lower()
    region = (request.args.get("region") or "").strip().lower()

    conn = get_db_connection()
    if query:
        like = f"%{query}%"
        rows = conn.execute(
            "SELECT id, country, city, region FROM destinations "
            "WHERE lower(city) LIKE ? OR lower(country) LIKE ? ORDER BY city",
            (like, like),
        ).fetchall()
    elif region:
        rows = conn.execute(
            "SELECT id, country, city, region FROM destinations "
            "WHERE lower(region) = ? ORDER BY city",
            (region,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, country, city, region FROM destinations ORDER BY city"
        ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])

@app.get("/destinations/<int:destination_id>")
def get_destination(destination_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT id, country, city, region FROM destinations WHERE id = ?",
        (destination_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Destination not found."}), 404

    return jsonify(dict(row))

@app.get("/destinations/<int:destination_id>/currency")
def get_currency(destination_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT currency_code, currency_name, exchange_tips "
        "FROM currency_infos WHERE destination_id = ?",
        (destination_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "No currency information for this destination."}), 404

    return jsonify(dict(row))

@app.get("/destinations/<int:destination_id>/transportation")
def get_transportation(destination_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT type, description, tips FROM transportation_infos "
        "WHERE destination_id = ? ORDER BY id",
        (destination_id,),
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])

@app.get("/destinations/<int:destination_id>/visa")
def get_visa(destination_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT nationality, requirement_type, notes FROM visa_requirements "
        "WHERE destination_id = ? ORDER BY nationality",
        (destination_id,),
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])

@app.get("/destinations/<int:destination_id>/weather")
def get_weather(destination_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT month, avg_temp, rainfall, best_visit_time FROM weather_infos "
        "WHERE destination_id = ? ORDER BY id",
        (destination_id,),
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])

@app.get("/destinations/<int:destination_id>/safety")
def get_safety(destination_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT safety_level, tips FROM safety_infos WHERE destination_id = ?",
        (destination_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "No safety information for this destination."}), 404

    return jsonify(dict(row))

@app.get("/feature-redirect-map")
def list_feature_redirect_map():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT keyword, feature_name, redirect_path_template "
        "FROM feature_redirect_map ORDER BY id"
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])

@app.post("/guide-chat-sessions")
def create_guide_chat_session():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    destination_id = payload.get("destination_id")

    if not user_id or not destination_id:
        return jsonify({"error": "Missing fields: user_id, destination_id"}), 400

    conn = get_db_connection()
    destination = conn.execute(
        "SELECT id FROM destinations WHERE id = ?", (destination_id,)
    ).fetchone()
    if destination is None:
        conn.close()
        return jsonify({"error": "Destination not found."}), 404

    created_at = now_iso()
    cursor = conn.execute(
        "INSERT INTO guide_ai_chat_sessions (user_id, destination_id, created_at) "
        "VALUES (?, ?, ?)",
        (user_id, destination_id, created_at),
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "id": session_id,
        "user_id": user_id,
        "destination_id": destination_id,
        "created_at": created_at,
    }), 201

@app.patch("/guide-chat-sessions/<int:session_id>")
def update_guide_chat_session(session_id):
    payload = request.get_json(silent=True) or {}
    destination_id = payload.get("destination_id")

    conn = get_db_connection()
    session_row = conn.execute(
        "SELECT id FROM guide_ai_chat_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session_row is None:
        conn.close()
        return jsonify({"error": "Chat session not found."}), 404

    if destination_id is not None:
        destination = conn.execute(
            "SELECT id FROM destinations WHERE id = ?", (destination_id,)
        ).fetchone()
        if destination is None:
            conn.close()
            return jsonify({"error": "Destination not found."}), 404

        conn.execute(
            "UPDATE guide_ai_chat_sessions SET destination_id = ? WHERE id = ?",
            (destination_id, session_id),
        )
        conn.commit()

    conn.close()
    return jsonify({"updated": True}), 200

@app.get("/guide-chat-sessions/<int:session_id>")
def get_guide_chat_session(session_id):
    conn = get_db_connection()
    session_row = conn.execute(
        "SELECT s.id, s.user_id, s.destination_id, s.created_at, d.city, d.country "
        "FROM guide_ai_chat_sessions s "
        "JOIN destinations d ON d.id = s.destination_id "
        "WHERE s.id = ?",
        (session_id,),
    ).fetchone()

    if session_row is None:
        conn.close()
        return jsonify({"error": "Chat session not found."}), 404

    messages = conn.execute(
        "SELECT id, role, content, intent_category, created_at "
        "FROM guide_ai_chat_messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()

    session = dict(session_row)
    session["messages"] = [dict(row) for row in messages]
    return jsonify(session)

@app.delete("/guide-chat-sessions/<int:session_id>")
def delete_guide_chat_session(session_id):
    conn = get_db_connection()
    session_row = conn.execute(
        "SELECT id FROM guide_ai_chat_sessions WHERE id = ?", (session_id,)
    ).fetchone()

    if session_row is None:
        conn.close()
        return jsonify({"error": "Chat session not found."}), 404

    conn.execute("DELETE FROM guide_ai_chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM guide_ai_chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

    return jsonify({"deleted": True}), 200

@app.post("/guide-chat-sessions/<int:session_id>/messages")
def add_guide_chat_message(session_id):
    payload = request.get_json(silent=True) or {}
    role = (payload.get("role") or "").strip()
    content = (payload.get("content") or "").strip()
    intent_category = payload.get("intent_category")

    if role not in ("user", "assistant"):
        return jsonify({"error": "role must be 'user' or 'assistant'."}), 400
    if not content:
        return jsonify({"error": "Missing field: content"}), 400

    conn = get_db_connection()
    session_row = conn.execute(
        "SELECT id FROM guide_ai_chat_sessions WHERE id = ?", (session_id,)
    ).fetchone()

    if session_row is None:
        conn.close()
        return jsonify({"error": "Chat session not found."}), 404

    created_at = now_iso()
    cursor = conn.execute(
        "INSERT INTO guide_ai_chat_messages "
        "(session_id, role, content, intent_category, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, intent_category, created_at),
    )
    conn.commit()
    message_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "intent_category": intent_category,
        "created_at": created_at,
    }), 201

@app.get("/users/<int:user_id>/guide-chat-sessions")
def list_user_guide_chat_sessions(user_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT s.id, s.destination_id, s.created_at, d.city, d.country "
        "FROM guide_ai_chat_sessions s "
        "JOIN destinations d ON d.id = s.destination_id "
        "WHERE s.user_id = ? ORDER BY s.id DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5204)
