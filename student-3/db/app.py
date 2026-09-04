"""Travel Mate database API (student-3, Tanishpreet Kour).
 
This service exclusively owns student3.db. Other backend/API microservices
must call these endpoints and must not open the SQLite file directly.
"""
 
import sqlite3
 
from flask import Flask, jsonify, request
 
app = Flask(__name__)
 
DATABASE_NAME = "./data/student3.db"
 
POST_FIELDS = (
    "traveller_id", "destination", "start_date", "end_date",
    "travel_style", "note", "status",
)
REQUEST_FIELDS = ("from_traveller_id", "to_post_id", "message", "status")
 
VALID_POST_STATUSES = {"open", "matched", "closed"}
VALID_REQUEST_STATUSES = {"pending", "accepted", "declined"}
 
 
def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
 
 
def rows_to_json(rows):
    return [dict(row) for row in rows]
 
 
@app.get("/health")
def health():
    conn = get_db_connection()
    posts = conn.execute("SELECT COUNT(*) AS n FROM trip_posts").fetchone()["n"]
    requests_count = conn.execute(
        "SELECT COUNT(*) AS n FROM connect_requests"
    ).fetchone()["n"]
    conn.close()
    return jsonify(
        {
            "service": "student-3-db",
            "status": "running",
            "trip_posts": posts,
            "connect_requests": requests_count,
        }
    )
 
 
# Trip posts --> full CRUD
 
def validate_post(payload, require_all=True):
    if require_all:
        missing = [f for f in POST_FIELDS if f not in ("status", "note") and payload.get(f) in (None, "")]
        if missing:
            return f"Missing fields: {', '.join(missing)}"
 
    status = payload.get("status")
    if status and status not in VALID_POST_STATUSES:
        return f"status must be one of: {', '.join(sorted(VALID_POST_STATUSES))}"
 
    start, end = payload.get("start_date"), payload.get("end_date")
    if start and end and end < start:
        return "end_date cannot be earlier than start_date"
 
    return None
 
 
@app.get("/trip_posts")
def list_trip_posts():
    destination = request.args.get("destination", "").strip()
    status = request.args.get("status", "").strip().lower()
    traveller_id = request.args.get("traveller_id", "").strip()
 
    query = "SELECT * FROM trip_posts"
    clauses, params = [], []
 
    if destination:
        clauses.append("LOWER(destination) LIKE ?")
        params.append(f"%{destination.lower()}%")
    if status:
        clauses.append("status = ?")
        params.append(status)
    if traveller_id.isdigit():
        clauses.append("traveller_id = ?")
        params.append(int(traveller_id))
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY start_date"
 
    conn = get_db_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_json(rows))
 
 
@app.get("/trip_posts/<int:post_id>")
def get_trip_post(post_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM trip_posts WHERE post_id = ?", (post_id,)
    ).fetchone()
    conn.close()
 
    if row is None:
        return jsonify({"error": "Trip post not found"}), 404
 
    return jsonify(dict(row))
 
 
@app.post("/trip_posts")
def create_trip_post():
    payload = request.get_json(silent=True) or {}
    error = validate_post(payload)
    if error:
        return jsonify({"error": error}), 400
 
    import datetime
    created_at = payload.get("created_at") or datetime.date.today().isoformat()
 
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO trip_posts "
        "(traveller_id, destination, start_date, end_date, travel_style, "
        "note, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            payload["traveller_id"],
            payload["destination"],
            payload["start_date"],
            payload["end_date"],
            payload["travel_style"],
            payload.get("note", ""),
            payload.get("status", "open"),
            created_at,
        ),
    )
    conn.commit()
    post_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM trip_posts WHERE post_id = ?", (post_id,)
    ).fetchone()
    conn.close()
 
    return jsonify(dict(row)), 201
 
 
@app.put("/trip_posts/<int:post_id>")
def update_trip_post(post_id):
    payload = request.get_json(silent=True) or {}
    updates = {f: payload[f] for f in POST_FIELDS if f in payload}
 
    if not updates:
        return jsonify({"error": "No updatable fields supplied"}), 400
 
    error = validate_post(payload, require_all=False)
    if error:
        return jsonify({"error": error}), 400
 
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT 1 FROM trip_posts WHERE post_id = ?", (post_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Trip post not found"}), 404
 
    conn.execute(
        f"UPDATE trip_posts SET {', '.join(f'{f} = ?' for f in updates)} "
        "WHERE post_id = ?",
        (*updates.values(), post_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM trip_posts WHERE post_id = ?", (post_id,)
    ).fetchone()
    conn.close()
 
    return jsonify(dict(row))
 
 
@app.delete("/trip_posts/<int:post_id>")
def delete_trip_post(post_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM connect_requests WHERE to_post_id = ?", (post_id,))
    cursor = conn.execute("DELETE FROM trip_posts WHERE post_id = ?", (post_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
 
    if not deleted:
        return jsonify({"error": "Trip post not found"}), 404
 
    return jsonify({"deleted": post_id})
 
 
# Connect requests: full CRUD 
 
def validate_request_payload(payload, require_all=True):
    if require_all:
        missing = [
            f for f in REQUEST_FIELDS
            if f != "status" and payload.get(f) in (None, "")
        ]
        if missing:
            return f"Missing fields: {', '.join(missing)}"
 
    status = payload.get("status")
    if status and status not in VALID_REQUEST_STATUSES:
        return f"status must be one of: {', '.join(sorted(VALID_REQUEST_STATUSES))}"
 
    return None
 
 
@app.get("/connect_requests")
def list_connect_requests():
    to_post_id = request.args.get("to_post_id", "").strip()
    from_traveller_id = request.args.get("from_traveller_id", "").strip()
    status = request.args.get("status", "").strip().lower()
 
    query = "SELECT * FROM connect_requests"
    clauses, params = [], []
 
    if to_post_id.isdigit():
        clauses.append("to_post_id = ?")
        params.append(int(to_post_id))
    if from_traveller_id.isdigit():
        clauses.append("from_traveller_id = ?")
        params.append(int(from_traveller_id))
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"
 
    conn = get_db_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(rows_to_json(rows))
 
 
@app.get("/connect_requests/<int:request_id>")
def get_connect_request(request_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM connect_requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    conn.close()
 
    if row is None:
        return jsonify({"error": "Connect request not found"}), 404
 
    return jsonify(dict(row))
 
 
@app.post("/connect_requests")
def create_connect_request():
    payload = request.get_json(silent=True) or {}
    error = validate_request_payload(payload)
    if error:
        return jsonify({"error": error}), 400
 
    conn = get_db_connection()
    post = conn.execute(
        "SELECT 1 FROM trip_posts WHERE post_id = ?", (payload["to_post_id"],)
    ).fetchone()
    if post is None:
        conn.close()
        return jsonify({"error": "Trip post not found for this request"}), 404
 
    import datetime
    created_at = payload.get("created_at") or datetime.date.today().isoformat()
 
    cursor = conn.execute(
        "INSERT INTO connect_requests "
        "(from_traveller_id, to_post_id, message, status, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            payload["from_traveller_id"],
            payload["to_post_id"],
            payload.get("message", ""),
            payload.get("status", "pending"),
            created_at,
        ),
    )
    conn.commit()
    request_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM connect_requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    conn.close()
 
    return jsonify(dict(row)), 201
 
 
@app.put("/connect_requests/<int:request_id>")
def update_connect_request(request_id):
    payload = request.get_json(silent=True) or {}
    updates = {f: payload[f] for f in REQUEST_FIELDS if f in payload}
 
    if not updates:
        return jsonify({"error": "No updatable fields supplied"}), 400
 
    error = validate_request_payload(payload, require_all=False)
    if error:
        return jsonify({"error": error}), 400
 
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT 1 FROM connect_requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Connect request not found"}), 404
 
    conn.execute(
        f"UPDATE connect_requests SET {', '.join(f'{f} = ?' for f in updates)} "
        "WHERE request_id = ?",
        (*updates.values(), request_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM connect_requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    conn.close()
 
    return jsonify(dict(row))
 
 
@app.delete("/connect_requests/<int:request_id>")
def delete_connect_request(request_id):
    conn = get_db_connection()
    cursor = conn.execute(
        "DELETE FROM connect_requests WHERE request_id = ?", (request_id,)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
 
    if not deleted:
        return jsonify({"error": "Connect request not found"}), 404
 
    return jsonify({"deleted": request_id})
 
 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5203)
