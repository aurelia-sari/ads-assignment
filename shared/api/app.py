"""Shared access API.

Centralises the functionality every feature needs so it is not duplicated five
times: traveller lookup (via shared-db) and a health view over the whole
integrated application.

Feature-specific data is NOT served here. Each student's database microservice
owns its own schema and exposes it through its own API.
"""

import os

import requests
from flask import Flask, jsonify
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
    ("student-2-api",     "http://student-2-api:5102/health", "Account & Dashboard"),
    ("student-2-db",      "http://student-2-db:5202/health",  "Account & Dashboard database"),
    ("student-3-api",     "http://student-3-api:5103/health", "Attractions & Dining"),
    ("student-3-db",      "http://student-3-db:5203/health",  "Attractions & Dining database"),
    ("student-4-api",     "http://student-4-api:5104/health", "Bookings & Budget"),
    ("student-4-db",      "http://student-4-db:5204/health",  "Bookings & Budget database"),
    ("student-5-api",     "http://student-5-api:5105/health", "Travel Mate"),
    ("student-5-db",      "http://student-5-db:5205/health",  "Travel Mate database"),
]


@app.get("/health")
def health():
    return jsonify({"service": "shared-api", "status": "running"})


@app.get("/services")
def services():
    return jsonify([{"name": name, "description": desc} for name, _, desc in SERVICES])


def probe(url):
    try:
        response = requests.get(url, timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


@app.get("/health/all")
def health_all():
    """HTMX fragment: one row per service in the integrated application."""
    rows = []
    up_count = 0

    for name, url, description in SERVICES:
        is_up = probe(url)
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
