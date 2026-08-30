"""Account & Dashboard backend/API (student-4, Aurelia Sari).

Serves the student-4 frontend (sign-up page + dashboard) and reaches the LLM
only through the shared AI-Mode service.

User accounts and access logs live in shared-db, not student-4-db: a user's
id and sign-in state are things any feature may need (not just Account &
Dashboard), the same cross-cutting role shared-db already plays for
traveller records. This service reaches them through shared-api, the same
way student-1 reaches traveller records - never shared-db directly.

student-4-db (DB_SERVICE_URL) is still this feature's own database, for
whatever Account & Dashboard-specific data isn't cross-cutting (e.g. saved
preferences, dashboard widgets) - it just doesn't hold users/access_logs.
"""

import os
import re
import secrets
from datetime import datetime, timezone
from html import escape

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash

app = Flask(__name__)
CORS(app)

DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://student-4-db:5204")
SHARED_API_URL = os.getenv("SHARED_API_URL", "http://shared-api:5000")
AI_MODE_URL = os.getenv("AI_MODE_URL", "http://ai-mode:5300")

DB_DOWN = "Could not reach the Account & Dashboard database service."
SHARED_DOWN = "Could not reach the shared access service."

LOCAL_PART_RE = re.compile(r"^(?!\.)(?!.*\.\.)[A-Za-z0-9._+-]+(?<!\.)$")
DOMAIN_RE = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")

def error_fragment(message, detail=""):
    body = f"<div class='notice notice-error'>{escape(message)}</div>"
    if detail:
        body += f"<pre>{escape(str(detail)[:600])}</pre>"
    return body

def validate_email(value):
    if not value or len(value) > 254 or value.count("@") != 1 or " " in value:
        return False

    local_part, domain = value.split("@")
    if not local_part or not domain:
        return False
    if len(local_part) > 64 or len(domain) > 255:
        return False

    return bool(LOCAL_PART_RE.match(local_part)) and bool(DOMAIN_RE.match(domain))

def validate_password(value):
    if not (8 <= len(value) <= 64):
        return False
    return (
        re.search(r"[A-Z]", value) is not None
        and re.search(r"[a-z]", value) is not None
        and re.search(r"[0-9]", value) is not None
        and re.search(r"[^A-Za-z0-9]", value) is not None
    )

def user_row(record):
    return (
        "<tr>"
        f"<td>{record['id']}</td>"
        f"<td>{escape(record['name'])}</td>"
        f"<td>{escape(record['email'])}</td>"
        "<td>"
        + (
            "<span class='pill pill-booked'>Verified</span>"
            if record["is_validated"]
            else "<span class='pill pill-planned'>Pending</span>"
        )
        + "</td>"
        f"<td>{escape(record['created_at'])}</td>"
        "</tr>"
    )

def users_table(users):
    if not users:
        return "<p class='muted'>No accounts yet.</p>"

    rows = "".join(user_row(u) for u in users)
    return (
        "<div class='table-wrap'><table>"
        "<thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Status</th><th>Joined</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
        f"<p class='muted'>{len(users)} account(s).</p>"
    )

@app.get("/health")
def health():
    return jsonify({"service": "student-4-api", "status": "running"})

@app.get("/users")
def list_users():
    try:
        response = requests.get(f"{SHARED_API_URL}/users", timeout=5)
        response.raise_for_status()
        return users_table(response.json()), 200
    except requests.RequestException as exc:
        return error_fragment(SHARED_DOWN, exc), 503

@app.post("/auth/register")
def register():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not name:
        return jsonify({"error": "Name is required."}), 400
    if not validate_email(email):
        return jsonify({"error": "Enter a valid email address."}), 400
    if not validate_password(password):
        return jsonify({"error": "Password must be 8-64 characters and include an "
                                  "uppercase letter, a lowercase letter, a number "
                                  "and a special character."}), 400

    verification_token = secrets.token_urlsafe(32)
    shared_payload = {
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "verification_token": verification_token,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    try:
        response = requests.post(f"{SHARED_API_URL}/users", json=shared_payload, timeout=5)
        if response.status_code == 409:
            return jsonify({"error": "This email is already associated with an account."}), 409
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": SHARED_DOWN, "detail": str(exc)[:300]}), 503

    user = response.json()

    # TODO (Aurelia Sari): send this link by email once a mail service is
    # wired up (e.g. SMTP or a transactional email API). Until then it is
    # handed back directly so register -> verify can be tested end-to-end.
    verification_link = f"/api/student-4/auth/verify/{verification_token}"

    return jsonify({**user, "verification_link": verification_link}), 201

@app.get("/auth/verify/<token>")
def verify(token):
    try:
        response = requests.post(f"{SHARED_API_URL}/users/verify/{token}", timeout=5)
        if response.status_code == 404:
            return error_fragment(
                "This verification link is invalid or has already been used."
            ), 404
        response.raise_for_status()
    except requests.RequestException as exc:
        return error_fragment(SHARED_DOWN, exc), 503

    return "<div class='notice notice-ok'>Email verified - you can now log in.</div>", 200

@app.post("/ai/chat")
def ai_chat():
    """AI-Mode integration. Flow: Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM."""
    question = request.form.get("question", "").strip()

    if not question:
        return error_fragment("Ask a question first."), 400
    try:
        response = requests.post(
            f"{AI_MODE_URL}/chat",
            json={"question": question, "context": ""},
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5104)
