"""Account & Dashboard database API (student-2, Aurelia Sari).

This service exclusively owns student2.db. Other backend/API microservices
must call these endpoints and must not open the SQLite file directly.

TODO (Aurelia Sari): replace the generic `records` resource with the real Account & Dashboard
resources.
"""

import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_NAME = "/app/data/student2.db"
FIELDS = ("title", "category", "detail", "created_on")


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/health")
def health():
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) AS n FROM records").fetchone()["n"]
    conn.close()
    return jsonify({"service": "student-2-db", "status": "running", "records": count})


@app.get("/records")
def list_records():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM records ORDER BY record_id").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.get("/records/<int:record_id>")
def get_record(record_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Record not found"}), 404

    return jsonify(dict(row))


@app.post("/records")
def create_record():
    payload = request.get_json(silent=True) or {}
    missing = [f for f in FIELDS if payload.get(f) in (None, "")]

    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    conn = get_db_connection()
    cursor = conn.execute(
        f"INSERT INTO records ({', '.join(FIELDS)}) VALUES (?, ?, ?, ?)",
        tuple(payload[f] for f in FIELDS),
    )
    conn.commit()
    record_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@app.put("/records/<int:record_id>")
def update_record(record_id):
    payload = request.get_json(silent=True) or {}
    updates = {f: payload[f] for f in FIELDS if f in payload}

    if not updates:
        return jsonify({"error": "No updatable fields supplied"}), 400

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT 1 FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Record not found"}), 404

    conn.execute(
        f"UPDATE records SET {', '.join(f'{f} = ?' for f in updates)} WHERE record_id = ?",
        (*updates.values(), record_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM records WHERE record_id = ?", (record_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row))


@app.delete("/records/<int:record_id>")
def delete_record(record_id):
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM records WHERE record_id = ?", (record_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if not deleted:
        return jsonify({"error": "Record not found"}), 404

    return jsonify({"deleted": record_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5202)
