"""Bookings & Budget database API (student-5, Aung Ko Khaing).

This service exclusively owns student5.db. Other backend/API microservices
must call these endpoints and must not open the SQLite file directly.
"""

import os
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)

# Path is relative to this script's own location so it works both inside
# Docker (WORKDIR /app -> resolves to /app/data) and when run locally.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATABASE_NAME = os.path.join(DATA_DIR, "student5.db")

BUDGET_FIELDS = ("total_budget", "flight_budget", "hotel_budget", "currency")
SELECTION_FIELDS = ("trip_id", "item_type", "item_id", "item_name", "price_aud")
HISTORY_FIELDS = (
    "trip_id", "search_type", "origin", "destination",
    "start_date", "end_date", "travellers", "budget_aud", "search_query",
)


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# =========================================================
# Health
# =========================================================

@app.get("/health")
def health():
    conn = get_db_connection()
    counts = {}
    for table in ("budgets", "flights", "hotels", "trip_selections", "search_history"):
        counts[table] = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    conn.close()
    return jsonify({"service": "student-5-db", "status": "running", "counts": counts})


# =========================================================
# Budgets
# =========================================================

@app.get("/budgets/<int:trip_id>")
def get_budget(trip_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM budgets WHERE trip_id = ? ORDER BY budget_id DESC LIMIT 1",
        (trip_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Budget not found"}), 404

    return jsonify(dict(row))


@app.post("/budgets")
def create_budget():
    payload = request.get_json(silent=True) or {}

    if "trip_id" not in payload or payload.get("total_budget") in (None, ""):
        return jsonify({"error": "Missing fields: trip_id, total_budget"}), 400

    trip_id = payload["trip_id"]
    total_budget = payload["total_budget"]
    flight_budget = payload.get("flight_budget", 0)
    hotel_budget = payload.get("hotel_budget", 0)
    currency = payload.get("currency", "AUD")
    timestamp = now_iso()

    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO budgets
        (trip_id, total_budget, flight_budget, hotel_budget, currency,
         created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (trip_id, total_budget, flight_budget, hotel_budget, currency,
         timestamp, timestamp),
    )
    conn.commit()
    budget_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM budgets WHERE budget_id = ?", (budget_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@app.put("/budgets/<int:trip_id>")
def update_budget(trip_id):
    """Upsert: updates the trip's budget if one exists, otherwise creates it."""
    payload = request.get_json(silent=True) or {}
    timestamp = now_iso()

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT * FROM budgets WHERE trip_id = ? ORDER BY budget_id DESC LIMIT 1",
        (trip_id,),
    ).fetchone()

    if existing is None:
        total_budget = payload.get("total_budget", 0)
        flight_budget = payload.get("flight_budget", 0)
        hotel_budget = payload.get("hotel_budget", 0)
        currency = payload.get("currency", "AUD")

        cursor = conn.execute(
            """
            INSERT INTO budgets
            (trip_id, total_budget, flight_budget, hotel_budget, currency,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (trip_id, total_budget, flight_budget, hotel_budget, currency,
             timestamp, timestamp),
        )
        conn.commit()
        budget_id = cursor.lastrowid
    else:
        updates = {f: payload[f] for f in BUDGET_FIELDS if f in payload}
        budget_id = existing["budget_id"]

        if updates:
            set_clause = ", ".join(f"{f} = ?" for f in updates)
            conn.execute(
                f"UPDATE budgets SET {set_clause}, updated_at = ? WHERE budget_id = ?",
                (*updates.values(), timestamp, budget_id),
            )
        else:
            conn.execute(
                "UPDATE budgets SET updated_at = ? WHERE budget_id = ?",
                (timestamp, budget_id),
            )
        conn.commit()

    row = conn.execute(
        "SELECT * FROM budgets WHERE budget_id = ?", (budget_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row))


# =========================================================
# Flight search
# =========================================================

@app.get("/flights/search")
def search_flights():
    args = request.args

    clauses = []
    params = []

    if args.get("destination"):
        clauses.append("LOWER(destination) LIKE LOWER(?)")
        params.append(f"%{args['destination']}%")

    if args.get("origin"):
        clauses.append("LOWER(origin) LIKE LOWER(?)")
        params.append(f"%{args['origin']}%")

    if args.get("start_date"):
        clauses.append("departure_date >= ?")
        params.append(args["start_date"])

    if args.get("end_date"):
        clauses.append("departure_date <= ?")
        params.append(args["end_date"])

    if args.get("budget_aud"):
        try:
            clauses.append("price_aud <= ?")
            params.append(float(args["budget_aud"]))
        except ValueError:
            pass

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = get_db_connection()
    rows = conn.execute(
        f"SELECT * FROM flights {where} ORDER BY flight_id", params
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


# =========================================================
# Hotel search
# =========================================================

@app.get("/hotels/search")
def search_hotels():
    args = request.args

    clauses = []
    params = []

    if args.get("destination"):
        clauses.append("LOWER(destination) LIKE LOWER(?)")
        params.append(f"%{args['destination']}%")

    if args.get("start_date"):
        clauses.append("check_out >= ?")
        params.append(args["start_date"])

    if args.get("end_date"):
        clauses.append("check_in <= ?")
        params.append(args["end_date"])

    if args.get("budget_aud"):
        try:
            clauses.append("total_price_aud <= ?")
            params.append(float(args["budget_aud"]))
        except ValueError:
            pass

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    conn = get_db_connection()
    rows = conn.execute(
        f"SELECT * FROM hotels {where} ORDER BY hotel_id", params
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


# =========================================================
# Trip selections
# =========================================================

@app.get("/selections/<int:trip_id>")
def get_selections(trip_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM trip_selections WHERE trip_id = ? ORDER BY selection_id",
        (trip_id,),
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


@app.post("/selections")
def add_selection():
    payload = request.get_json(silent=True) or {}
    missing = [f for f in SELECTION_FIELDS if payload.get(f) in (None, "")]

    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    if payload["item_type"] not in ("flight", "hotel"):
        return jsonify({"error": "item_type must be 'flight' or 'hotel'"}), 400

    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO trip_selections
        (trip_id, item_type, item_id, item_name, price_aud, selected_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            payload["trip_id"], payload["item_type"], payload["item_id"],
            payload["item_name"], payload["price_aud"], now_iso(),
        ),
    )
    conn.commit()
    selection_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM trip_selections WHERE selection_id = ?", (selection_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@app.delete("/selections/<int:selection_id>")
def remove_selection(selection_id):
    conn = get_db_connection()
    cursor = conn.execute(
        "DELETE FROM trip_selections WHERE selection_id = ?", (selection_id,)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if not deleted:
        return jsonify({"error": "Selection not found"}), 404

    return jsonify({"deleted": selection_id})


# =========================================================
# Search history
# =========================================================

@app.get("/search-history/<int:trip_id>")
def get_search_history(trip_id):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM search_history WHERE trip_id = ? ORDER BY search_id DESC",
        (trip_id,),
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


@app.post("/search-history")
def create_search_history():
    payload = request.get_json(silent=True) or {}

    if payload.get("trip_id") in (None, "") or payload.get("destination") in (None, ""):
        return jsonify({"error": "Missing fields: trip_id, destination"}), 400

    values = {f: payload.get(f) for f in HISTORY_FIELDS}
    values["travellers"] = values.get("travellers") or 1

    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO search_history
        (trip_id, search_type, origin, destination, start_date, end_date,
         travellers, budget_aud, search_query, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            values["trip_id"], values["search_type"], values["origin"],
            values["destination"], values["start_date"], values["end_date"],
            values["travellers"], values["budget_aud"], values["search_query"],
            now_iso(),
        ),
    )
    conn.commit()
    search_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM search_history WHERE search_id = ?", (search_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5205)