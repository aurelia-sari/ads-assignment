"""Shared access database API.

This service exclusively owns the shared access schema. No other service may
open shared.db directly; every read or write goes through this HTTP API.
"""

import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_NAME = "/app/data/shared.db"

TRAVELLER_FIELDS = ("full_name", "email", "home_city", "member_since")
USER_FIELDS = ("name", "email", "password_hash", "verification_token", "created_at")


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/health")
def health():
    return jsonify({"service": "shared-db", "status": "running"})


@app.get("/travellers")
def list_travellers():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM travellers ORDER BY traveller_id"
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.get("/travellers/<int:traveller_id>")
def get_traveller(traveller_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM travellers WHERE traveller_id = ?", (traveller_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Traveller not found"}), 404

    return jsonify(dict(row))


@app.post("/travellers")
def create_traveller():
    payload = request.get_json(silent=True) or {}
    missing = [field for field in TRAVELLER_FIELDS if not payload.get(field)]

    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO travellers (full_name, email, home_city, member_since)
            VALUES (?, ?, ?, ?)
            """,
            tuple(payload[field] for field in TRAVELLER_FIELDS),
        )
        conn.commit()
        traveller_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "A traveller with that email already exists"}), 409
    conn.close()

    return jsonify({"traveller_id": traveller_id}), 201


@app.delete("/travellers/<int:traveller_id>")
def delete_traveller(traveller_id):
    conn = get_db_connection()
    cursor = conn.execute(
        "DELETE FROM travellers WHERE traveller_id = ?", (traveller_id,)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if not deleted:
        return jsonify({"error": "Traveller not found"}), 404

    return jsonify({"deleted": traveller_id})


# Users & access logs
def user_public(row):
    """Drop the password hash and verification token before handing a user
    row back to a caller."""
    data = dict(row)
    data.pop("password_hash", None)
    data.pop("verification_token", None)
    return data


@app.get("/users")
def list_users():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([user_public(row) for row in rows])


@app.get("/users/by-email/<path:email>")
def get_user_by_email(email):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user_public(row))


@app.post("/users")
def create_user():
    payload = request.get_json(silent=True) or {}
    missing = [
        f for f in USER_FIELDS if f != "verification_token" and payload.get(f) in (None, "")
    ]

    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            f"INSERT INTO users ({', '.join(USER_FIELDS)}) VALUES (?, ?, ?, ?, ?)",
            tuple(payload.get(f) for f in USER_FIELDS),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Email already registered"}), 409

    user_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return jsonify(user_public(row)), 201


@app.post("/users/verify/<token>")
def verify_user(token):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE verification_token = ?", (token,)
    ).fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "Invalid or already-used verification link"}), 404

    conn.execute(
        "UPDATE users SET is_validated = 1, verification_token = NULL WHERE id = ?",
        (row["id"],),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
    conn.close()

    return jsonify(user_public(updated))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5200)
