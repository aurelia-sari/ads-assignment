"""
Attractions & Dining backend/API (student-2, Kevin Kim).

Serves HTMX fragments to the student-2 frontend.

Architecture

Frontend (HTMX)
        │
        ▼
Student-2 Backend/API
        │
        ├── Student-2 Database API
        └── Shared AI-Mode Service

This service never accesses SQLite directly.
All database operations must go through the Student-2 Database API.
"""

import os

from flask import Flask, jsonify
from flask_cors import CORS

from routes.normal_ui import normal_ui_bp
# from routes.ai_mode import ai_mode_bp

app = Flask(__name__)
CORS(app)

# Configuration
app.config["DB_SERVICE_URL"] = os.getenv(
    "DB_SERVICE_URL",
    "http://student-2-db:5202",
)

app.config["AI_MODE_URL"] = os.getenv(
    "AI_MODE_URL",
    "http://ai-mode:5300",
)

# Blueprints
app.register_blueprint(normal_ui_bp)
# app.register_blueprint(ai_mode_bp)

# Health
@app.get("/health")
def health():
    return jsonify(
        {
            "service": "student-2-api",
            "status": "running",
        }
    )


# Entry Point
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5102,
    )