"""Account & Dashboard database API (student-4, Aurelia Sari).

This service exclusively owns student4.db. Other backend/API microservices
must call these endpoints and must not open the SQLite file directly.

No domain tables yet - user accounts and access logs live in shared-db
instead (see shared/db/app.py), since a user's id and sign-in state are
cross-cutting data every feature may need. This service is ready for
whatever Account & Dashboard-specific data comes next.
"""

import sqlite3

from flask import Flask, jsonify

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5204)
