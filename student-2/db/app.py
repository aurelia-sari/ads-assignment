"""
TODO (Kevin Kim): replace the generic `records` resource with the real Attractions & Dining
resources.
"""

"""
Attractions & Dining database API (Student 2 - Kevin Kim).

This service exclusively owns student2.db.
Other backend/API microservices must access the database
through these API endpoints and must not open the SQLite file directly.

Resources:
- places
- favourites
- recommendations
"""

import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_NAME = "/app/data/student2.db"

# Fields used when creating or updating a place.
PLACE_FIELDS = (
    "name",
    "category",
    "address",
    "rating",
    "opening_hours",
    "price_range",
    "description",
)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@app.get("/health")
def health():
    conn = get_db_connection()

    places_count = conn.execute(
        "SELECT COUNT(*) AS n FROM places"
    ).fetchone()["n"]

    favourites_count = conn.execute(
        "SELECT COUNT(*) AS n FROM favourites"
    ).fetchone()["n"]

    recommendations_count = conn.execute(
        "SELECT COUNT(*) AS n FROM recommendations"
    ).fetchone()["n"]

    conn.close()

    return jsonify({
        "service": "student-2-db",
        "status": "running",
        "places": places_count,
        "favourites": favourites_count,
        "recommendations": recommendations_count,
    })

# ===========================
# View
# ===========================

# View places
@app.get("/places")
def get_places():
    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            external_place_id,
            name,
            category,
            address,
            latitude,
            longitude,
            rating,
            opening_hours,
            price_range,
            description,
            image_url
        FROM places
        ORDER BY rating DESC, name ASC
        """
    ).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])

# View favorites
@app.get("/favourites")
def get_favourites():
    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT
            favourites.id,
            favourites.user_id,
            favourites.place_id,
            favourites.notes,
            favourites.created_at,
            places.name AS place_name,
            places.category,
            places.address,
            places.rating,
            places.price_range,
            places.image_url
        FROM favourites
        JOIN places
            ON favourites.place_id = places.id
        ORDER BY favourites.created_at DESC
        """
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

# ------------------------------------------------------------------
# For smoke_test.py
# ------------------------------------------------------------------
FIELDS = ("title", "category", "detail", "created_on")

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

# ------------------------------------------------------------------
# For smoke_test.py
# ------------------------------------------------------------------



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5202)
