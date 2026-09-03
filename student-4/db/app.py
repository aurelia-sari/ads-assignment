"""Account & Dashboard database API (student-4, Aurelia Sari).

This service exclusively owns student4.db. Other backend/API microservices
must call these endpoints and must not open the SQLite file directly.

User accounts and access logs live in shared-db instead (see
shared/db/app.py), since a user's id and sign-in state are cross-cutting
data every feature may need. This service owns the Travel Guides.
"""

import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_NAME = "/app/data/student4.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5204)
