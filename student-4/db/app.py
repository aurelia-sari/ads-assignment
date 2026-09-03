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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5204)
