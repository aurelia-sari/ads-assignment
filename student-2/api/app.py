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
import requests

from html import escape
from flask import Flask, jsonify, request
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
    
    
# ------------------------------------------------------------------
# For smoke_test.py
# ------------------------------------------------------------------

DB_SERVICE_URL = app.config["DB_SERVICE_URL"]
AI_MODE_URL = app.config["AI_MODE_URL"]
DB_DOWN = "Could not reach the Attractions & Dining database service."

def error_fragment(message, detail=""):
    body = f"<div class='notice notice-error'>{escape(message)}</div>"
    if detail:
        body += f"<pre>{escape(str(detail)[:600])}</pre>"
    return body


def records_table(records):
    if not records:
        return "<p class='muted'>No records yet.</p>"

    rows = "".join(
        "<tr>"
        f"<td>{record['record_id']}</td>"
        f"<td>{escape(record['title'])}</td>"
        f"<td>{escape(record['category'])}</td>"
        f"<td style='white-space:normal'>{escape(record['detail'])}</td>"
        f"<td>{escape(record['created_on'])}</td>"
        "<td>"
        f"<button class='btn-sm btn-danger' hx-delete='/api/student-2/records/{record['record_id']}' "
        "hx-target='#records-panel' hx-swap='innerHTML'>Delete</button>"
        "</td></tr>"
        for record in records
    )
    return (
        "<div class='table-wrap'><table>"
        "<thead><tr><th>ID</th><th>Title</th><th>Category</th><th>Detail</th>"
        "<th>Created</th><th></th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
        f"<p class='muted'>{len(records)} record(s).</p>"
    )

def fetch_records():
    response = requests.get(f"{DB_SERVICE_URL}/records", timeout=5)
    response.raise_for_status()
    return response.json()


@app.get("/records")
def list_records():
    try:
        return records_table(fetch_records()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@app.post("/records")
def create_record():
    payload = {key: value.strip() for key, value in request.form.items()}
    try:
        response = requests.post(f"{DB_SERVICE_URL}/records", json=payload, timeout=5)
        if response.status_code == 400:
            return error_fragment(response.json().get("error", "Invalid record.")), 400
        response.raise_for_status()
        return records_table(fetch_records()), 201
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@app.delete("/records/<int:record_id>")
def delete_record(record_id):
    try:
        response = requests.delete(
            f"{DB_SERVICE_URL}/records/{record_id}", timeout=5
        )
        if response.status_code == 404:
            return error_fragment("Record not found."), 404
        response.raise_for_status()
        return records_table(fetch_records()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@app.post("/ai/chat")
def ai_chat():
    """AI-Mode integration. Flow: Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM."""
    question = request.form.get("question", "").strip()

    if not question:
        return error_fragment("Ask a question first."), 400

    try:
        records = fetch_records()
        context = "\n".join(
            f"  {r['title']} ({r['category']}): {r['detail']}" for r in records[:10]
        )
    except requests.RequestException:
        context = ""

    try:
        response = requests.post(
            f"{AI_MODE_URL}/chat",
            json={"question": question, "context": context},
            timeout=180,
        )
        response.raise_for_status()
        answer = response.json()["answer"]
        return (
            "<div class='chat-msg user'><div class='who'>You</div>"
            f"<div class='bubble'>{escape(question)}</div></div>"
            "<div class='chat-msg bot'><div class='who'>NextStop AI</div>"
            f"<div class='bubble'>{escape(answer)}</div></div>"
        ), 200
    except requests.RequestException as exc:
        return error_fragment("Could not reach the AI-Mode service.", exc), 503


# ------------------------------------------------------------------
# For smoke_test.py
# ------------------------------------------------------------------



# Entry Point
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5102,
    )