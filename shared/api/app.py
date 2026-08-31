"""Shared access API.

Centralises the functionality every feature needs so it is not duplicated five
times: traveller lookup, user/session lookup (both via shared-db), and a
health view over the whole integrated application.

Feature-specific data is NOT served here. Each student's database microservice
owns its own schema and exposes it through its own API.
"""

import os
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SHARED_DB_URL = os.getenv("SHARED_DB_URL", "http://shared-db:5200")

# The integrated application, as one place the team can check.
SERVICES = [
    ("shared-db",         "http://shared-db:5200/health",     "Shared access database"),
    ("ai-mode",           "http://ai-mode:5300/health",       "Shared AI-Mode service"),
    ("student-1-api",     "http://student-1-api:5101/health", "Trips & Itinerary"),
    ("student-1-db",      "http://student-1-db:5201/health",  "Trips & Itinerary database"),
    ("student-2-api",     "http://student-2-api:5102/health", "Attractions & Dining"),
    ("student-2-db",      "http://student-2-db:5202/health",  "Attractions & Dining database"),
    ("student-3-api",     "http://student-3-api:5103/health", "Travel Mate"),
    ("student-3-db",      "http://student-3-db:5203/health",  "Travel Mate database"),
    ("student-4-api",     "http://student-4-api:5104/health", "Account & Dashboard"),
    ("student-4-db",      "http://student-4-db:5204/health",  "Account & Dashboard database"),
    ("student-5-api",     "http://student-5-api:5105/health", "Bookings & Budget"),
    ("student-5-db",      "http://student-5-db:5205/health",  "Bookings & Budget database"),
    ("shared-frontend",    "http://shared-frontend:80/health",    "Unified home page"),
    ("student-1-frontend", "http://student-1-frontend:80/health", "Trips & Itinerary page"),
    ("student-2-frontend", "http://student-2-frontend:80/health", "Attractions & Dining page"),
    ("student-3-frontend", "http://student-3-frontend:80/health", "Travel Mate page"),
    ("student-4-frontend", "http://student-4-frontend:80/health", "Account & Dashboard page"),
    ("student-5-frontend", "http://student-5-frontend:80/health", "Bookings & Budget page"),
]

@app.get("/health")
def health():
    return jsonify({"service": "shared-api", "status": "running"})

@app.get("/services")
def services():
    return jsonify([{"name": name, "description": desc} for name, _, desc in SERVICES])

# Probes run concurrently with a tolerant timeout. A short sequential probe
# reported healthy services as down whenever the host was busy serving the LLM,
# which is exactly when someone is demonstrating the application.
PROBE_TIMEOUT_SECONDS = 6

def probe(url):
    try:
        response = requests.get(url, timeout=PROBE_TIMEOUT_SECONDS)
        return response.status_code == 200
    except requests.RequestException:
        return False

@app.get("/health/all")
def health_all():
    """HTMX fragment: one row per service in the integrated application."""
    with ThreadPoolExecutor(max_workers=len(SERVICES)) as pool:
        results = list(pool.map(probe, [url for _, url, _ in SERVICES]))

    rows = []
    up_count = 0

    for (name, _url, description), is_up in zip(SERVICES, results):
        up_count += is_up
        pill = "pill-booked" if is_up else "pill-cancelled"
        label = "up" if is_up else "down"
        rows.append(
            f"<tr><td>{name}</td><td class='muted'>{description}</td>"
            f"<td><span class='pill {pill}'>{label}</span></td></tr>"
        )

    summary = f"<p class='muted'>{up_count} of {len(SERVICES)} services up.</p>"
    table = (
        "<div class='table-wrap'><table>"
        "<thead><tr><th>Service</th><th>Feature</th><th>Status</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )
    return summary + table

@app.get("/travellers")
def travellers():
    try:
        response = requests.get(f"{SHARED_DB_URL}/travellers", timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

@app.get("/travellers/<int:traveller_id>")
def traveller(traveller_id):
    try:
        response = requests.get(
            f"{SHARED_DB_URL}/travellers/{traveller_id}", timeout=5
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

# Users & access logs
@app.get("/users")
def users():
    try:
        response = requests.get(f"{SHARED_DB_URL}/users", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

@app.get("/users/by-email/<path:email>")
def user_by_email(email):
    try:
        response = requests.get(f"{SHARED_DB_URL}/users/by-email/{email}", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

@app.post("/users")
def create_user():
    try:
        response = requests.post(
            f"{SHARED_DB_URL}/users", json=request.get_json(silent=True) or {}, timeout=5
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

@app.post("/users/verify/<token>")
def verify_user(token):
    try:
        response = requests.post(f"{SHARED_DB_URL}/users/verify/{token}", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

@app.post("/users/verification/resend")
def resend_verification():
    try:
        response = requests.post(
            f"{SHARED_DB_URL}/users/verification/resend",
            json=request.get_json(silent=True) or {},
            timeout=5,
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

@app.post("/users/authenticate")
def authenticate_user():
    try:
        response = requests.post(
            f"{SHARED_DB_URL}/users/authenticate",
            json=request.get_json(silent=True) or {},
            timeout=5,
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

@app.post("/access-logs")
def create_access_log():
    try:
        response = requests.post(
            f"{SHARED_DB_URL}/access-logs",
            json=request.get_json(silent=True) or {},
            timeout=5,
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

@app.post("/access-logs/sign-out")
def sign_out():
    try:
        response = requests.post(
            f"{SHARED_DB_URL}/access-logs/sign-out",
            json=request.get_json(silent=True) or {},
            timeout=5,
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

@app.get("/access-logs/status/<int:user_id>")
def session_status(user_id):
    try:
        response = requests.get(
            f"{SHARED_DB_URL}/access-logs/status/{user_id}", timeout=5
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": "shared-db unavailable", "detail": str(exc)}), 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
