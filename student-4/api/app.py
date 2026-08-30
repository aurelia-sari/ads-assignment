"""Account & Dashboard backend/API (student-4, Aurelia Sari).

Serves the student-4 frontend (sign-up page + dashboard) and reaches the LLM
only through the shared AI-Mode service.

User accounts and access logs live in shared-db, not student-4-db: a user's
id and sign-in state are things any feature may need (not just Account &
Dashboard). This service reaches them through shared-api.

Verification emails go through Mailpit locally. Swap for Resend in a later release, 
only send_verification_email below should need to change.
"""

import os
import re
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
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

MAILPIT_HOST = os.getenv("MAILPIT_HOST", "mailpit")
MAILPIT_PORT = int(os.getenv("MAILPIT_PORT", "1025"))
MAIL_FROM = os.getenv("MAIL_FROM", "no-reply@nextstop.local")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8080")

DB_DOWN = "Could not reach the Account & Dashboard database service."
SHARED_DOWN = "Could not reach the shared access service."

VERIFY_TOKEN_TTL_MINUTES = 5

LOCAL_PART_RE = re.compile(r"^(?!\.)(?!.*\.\.)[A-Za-z0-9._+-]+(?<!\.)$")
DOMAIN_RE = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")

ENVELOPE_SVG = (
    "<svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round'>"
    "<rect x='3' y='5' width='18' height='14' rx='2'/><path d='M3 7l9 6 9-6'/></svg>"
)

def error_fragment(message, detail=""):
    body = f"<div class='notice notice-error'>{escape(message)}</div>"
    if detail:
        body += f"<pre>{escape(str(detail)[:600])}</pre>"
    return body

def verify_page(heading, message, tone, status=200, cta_href="/", cta_label="Back to NextStop"):
    pill = "notice-ok" if tone == "ok" else "notice-error"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(heading)} - NextStop</title>
<link rel="stylesheet" href="/shared/css/theme.css">
</head>
<body class="verify-body">
<main class="verify-card">
  <div class="verify-icon">{ENVELOPE_SVG}</div>
  <h1 class="verify-title">{escape(heading)}</h1>
  <p class="notice {pill} notice--top-gap">{escape(message)}</p>
  <a class="btn btn--pill-dark verify-resend" href="{escape(cta_href)}">{escape(cta_label)}</a>
</main>
</body>
</html>"""
    return html, status

def new_verification_token():
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=VERIFY_TOKEN_TTL_MINUTES)
    ).isoformat(timespec="seconds")
    return token, expires_at

def send_verification_email(name, email, token):
    verify_url = f"{PUBLIC_BASE_URL}/api/student-4/auth/verify/{token}"
    body = (
        f"Hi {name},\n\n"
        "Welcome to NextStop! Click the link below to verify your email address.\n\n"
        f"{verify_url}\n\n"
        f"This link can only be used once and expires in {VERIFY_TOKEN_TTL_MINUTES} minutes.\n"
        "If you didn't request this, you can safely ignore this email."
    )
    message = MIMEText(body)
    message["Subject"] = "Verify your NextStop account"
    message["From"] = MAIL_FROM
    message["To"] = email

    with smtplib.SMTP(MAILPIT_HOST, MAILPIT_PORT, timeout=5) as smtp:
        smtp.send_message(message)

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
    terms_accepted = payload.get("terms_accepted")

    if not name:
        return jsonify({"error": "Name is required."}), 400
    if not validate_email(email):
        return jsonify({"error": "Enter a valid email address."}), 400
    if not validate_password(password):
        return jsonify({"error": "Password must be 8-64 characters and include an "
                                  "uppercase letter, a lowercase letter, a number "
                                  "and a special character."}), 400
    if not terms_accepted:
        return jsonify({"error": "You must agree to the Terms and Conditions."}), 400

    verification_token, verification_expires_at = new_verification_token()
    shared_payload = {
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "verification_token": verification_token,
        "verification_expires_at": verification_expires_at,
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

    try:
        send_verification_email(name, email, verification_token)
    except OSError as exc:
        print(f"[student-4-api] failed to send verification email: {exc}")

    return jsonify(user), 201

def issue_verification_email(email):
    """Generate a fresh verification token, register it with shared-api, and
    send it. Shared between /auth/resend (explicit user request) and
    /auth/login (an unverified account trying to sign in also needs an email
    in their inbox to act on, not just a screen telling them to check it)."""
    verification_token, verification_expires_at = new_verification_token()

    try:
        response = requests.post(
            f"{SHARED_API_URL}/users/verification/resend",
            json={
                "email": email,
                "verification_token": verification_token,
                "verification_expires_at": verification_expires_at,
            },
            timeout=5,
        )
        data = response.json()
    except requests.RequestException as exc:
        return jsonify({"error": SHARED_DOWN, "detail": str(exc)[:300]}), 503

    if response.status_code != 200:
        return jsonify(data), response.status_code

    try:
        send_verification_email("there", email, verification_token)
    except OSError as exc:
        return jsonify({"error": "Could not send the email. Please try again."}), 503

    return jsonify({"resent": True}), 200

@app.post("/auth/resend")
def resend():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()

    if not validate_email(email):
        return jsonify({"error": "Enter a valid email address."}), 400

    return issue_verification_email(email)

@app.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    generic_error = jsonify({"error": "Invalid email or password."}), 401

    if not validate_email(email) or not password:
        return generic_error

    try:
        response = requests.post(
            f"{SHARED_API_URL}/users/authenticate",
            json={"email": email, "password": password},
            timeout=5,
        )
        data = response.json()
    except requests.RequestException as exc:
        return jsonify({"error": SHARED_DOWN, "detail": str(exc)[:300]}), 503

    if response.status_code == 403:
        # An unverified account trying to sign in needs an email
        # to act on, not just a "check your email" screen.
        issue_verification_email(email)
        return jsonify(data), 403
    if response.status_code != 200:
        return generic_error

    user = data

    try:
        log_response = requests.post(
            f"{SHARED_API_URL}/access-logs", json={"user_id": user["id"]}, timeout=5
        )
        log_response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": SHARED_DOWN, "detail": str(exc)[:300]}), 503

    return jsonify(user), 200

@app.get("/auth/verify/<token>")
def verify(token):
    try:
        response = requests.post(f"{SHARED_API_URL}/users/verify/{token}", timeout=5)
    except requests.RequestException as exc:
        return verify_page("Verification unavailable", SHARED_DOWN, "error", 503)

    if response.status_code == 404:
        return verify_page(
            "Link invalid",
            "This verification link is invalid or has already been used.",
            "error",
            404,
        )
    if response.status_code == 410:
        return verify_page(
            "Link expired",
            "This verification link has expired. Please request a new one.",
            "error",
            410,
        )
    if response.status_code != 200:
        return verify_page("Verification unavailable", SHARED_DOWN, "error", 503)

    return verify_page(
        "Email verified", "You can now log in to your account.", "ok", 200,
        cta_href="/student-4/signin.html", cta_label="Sign in",
    )

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
