"""Shared access database API.

This service exclusively owns the shared access schema. No other service may
open shared.db directly; every read or write goes through this HTTP API.
"""

import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_NAME = "/app/data/shared.db"

TRAVELLER_FIELDS = ("full_name", "email", "home_city", "member_since")


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5200)
