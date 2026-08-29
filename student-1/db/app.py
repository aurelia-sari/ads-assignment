"""Trips & Itinerary database API (student-1).

This service exclusively owns trips.db. Other backend/API microservices that
need trip or itinerary data must call these endpoints; they must not open the
SQLite file, tables, or schema directly.
"""

import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_NAME = "/app/data/trips.db"

TRIP_FIELDS = (
    "trip_name", "destination", "start_date", "end_date",
    "traveller_id", "budget_aud", "status",
)
DAY_FIELDS = ("trip_id", "day_number", "day_date", "location", "activity", "notes")

VALID_STATUSES = {"planned", "booked", "completed", "cancelled"}


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
    trips = conn.execute("SELECT COUNT(*) AS n FROM trips").fetchone()["n"]
    days = conn.execute("SELECT COUNT(*) AS n FROM itinerary_days").fetchone()["n"]
    conn.close()
    return jsonify(
        {"service": "student-1-db", "status": "running", "trips": trips, "itinerary_days": days}
    )


# --- Trips: full CRUD -----------------------------------------------------

@app.get("/trips")
def list_trips():
    destination = request.args.get("destination", "").strip()
    status = request.args.get("status", "").strip().lower()
    traveller_id = request.args.get("traveller_id", "").strip()

    query = "SELECT * FROM trips"
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


@app.get("/trips/<int:trip_id>")
def get_trip(trip_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM trips WHERE trip_id = ?", (trip_id,)).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Trip not found"}), 404

    return jsonify(dict(row))


def validate_trip(payload, require_all=True):
    if require_all:
        missing = [f for f in TRIP_FIELDS if payload.get(f) in (None, "")]
        if missing:
            return f"Missing fields: {', '.join(missing)}"

    status = payload.get("status")
    if status and status not in VALID_STATUSES:
        return f"status must be one of: {', '.join(sorted(VALID_STATUSES))}"

    start, end = payload.get("start_date"), payload.get("end_date")
    if start and end and end < start:
        return "end_date cannot be earlier than start_date"

    return None


@app.post("/trips")
def create_trip():
    payload = request.get_json(silent=True) or {}
    error = validate_trip(payload)
    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()
    cursor = conn.execute(
        f"INSERT INTO trips ({', '.join(TRIP_FIELDS)}) "
        f"VALUES ({', '.join('?' for _ in TRIP_FIELDS)})",
        tuple(payload[f] for f in TRIP_FIELDS),
    )
    conn.commit()
    trip_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM trips WHERE trip_id = ?", (trip_id,)).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@app.put("/trips/<int:trip_id>")
def update_trip(trip_id):
    payload = request.get_json(silent=True) or {}
    updates = {f: payload[f] for f in TRIP_FIELDS if f in payload}

    if not updates:
        return jsonify({"error": "No updatable fields supplied"}), 400

    error = validate_trip(payload, require_all=False)
    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()
    existing = conn.execute("SELECT 1 FROM trips WHERE trip_id = ?", (trip_id,)).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Trip not found"}), 404

    conn.execute(
        f"UPDATE trips SET {', '.join(f'{f} = ?' for f in updates)} WHERE trip_id = ?",
        (*updates.values(), trip_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM trips WHERE trip_id = ?", (trip_id,)).fetchone()
    conn.close()

    return jsonify(dict(row))


@app.delete("/trips/<int:trip_id>")
def delete_trip(trip_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM itinerary_days WHERE trip_id = ?", (trip_id,))
    cursor = conn.execute("DELETE FROM trips WHERE trip_id = ?", (trip_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if not deleted:
        return jsonify({"error": "Trip not found"}), 404

    return jsonify({"deleted": trip_id})


# --- Itinerary days: full CRUD -------------------------------------------

@app.get("/days")
def list_days():
    trip_id = request.args.get("trip_id")

    conn = get_db_connection()
    if trip_id:
        rows = conn.execute(
            "SELECT * FROM itinerary_days WHERE trip_id = ? ORDER BY day_number",
            (trip_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM itinerary_days ORDER BY trip_id, day_number"
        ).fetchall()
    conn.close()
    return jsonify(rows_to_json(rows))


@app.get("/days/<int:day_id>")
def get_day(day_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM itinerary_days WHERE day_id = ?", (day_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Itinerary day not found"}), 404

    return jsonify(dict(row))


@app.post("/days")
def create_day():
    payload = request.get_json(silent=True) or {}
    required = ("trip_id", "day_number", "day_date", "location", "activity")
    missing = [f for f in required if payload.get(f) in (None, "")]

    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    conn = get_db_connection()
    trip = conn.execute(
        "SELECT 1 FROM trips WHERE trip_id = ?", (payload["trip_id"],)
    ).fetchone()
    if trip is None:
        conn.close()
        return jsonify({"error": "Trip not found for this itinerary day"}), 404

    cursor = conn.execute(
        f"INSERT INTO itinerary_days ({', '.join(DAY_FIELDS)}) "
        f"VALUES ({', '.join('?' for _ in DAY_FIELDS)})",
        tuple(payload.get(f, "") for f in DAY_FIELDS),
    )
    conn.commit()
    day_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM itinerary_days WHERE day_id = ?", (day_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@app.put("/days/<int:day_id>")
def update_day(day_id):
    payload = request.get_json(silent=True) or {}
    updates = {f: payload[f] for f in DAY_FIELDS if f in payload}

    if not updates:
        return jsonify({"error": "No updatable fields supplied"}), 400

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT 1 FROM itinerary_days WHERE day_id = ?", (day_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Itinerary day not found"}), 404

    conn.execute(
        f"UPDATE itinerary_days SET {', '.join(f'{f} = ?' for f in updates)} "
        "WHERE day_id = ?",
        (*updates.values(), day_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM itinerary_days WHERE day_id = ?", (day_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row))


@app.delete("/days/<int:day_id>")
def delete_day(day_id):
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM itinerary_days WHERE day_id = ?", (day_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if not deleted:
        return jsonify({"error": "Itinerary day not found"}), 404

    return jsonify({"deleted": day_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5201)
