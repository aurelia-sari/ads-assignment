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
from urllib.parse import quote

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash

from routes.ai_chat import ai_chat_bp
from routes.ai_tools import ai_tools_bp
from routes.live_guides import live_guides_bp
from services.weather import local_month
from views.live_guides_formatter import live_rates_placeholder, live_weather_placeholder

app = Flask(__name__)
CORS(app)
app.register_blueprint(ai_chat_bp)
app.register_blueprint(ai_tools_bp)
app.register_blueprint(live_guides_bp)

DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://student-4-db:5204")
SHARED_API_URL = os.getenv("SHARED_API_URL", "http://shared-api:5000")

MAILPIT_HOST = os.getenv("MAILPIT_HOST", "mailpit")
MAILPIT_PORT = int(os.getenv("MAILPIT_PORT", "1025"))
MAIL_FROM = os.getenv("MAIL_FROM", "no-reply@nextstop.local")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8080")

DB_DOWN = "Could not reach the Account & Dashboard database service."
SHARED_DOWN = "Could not reach the shared access service."

VERIFY_TOKEN_TTL_MINUTES = 5
RESET_TOKEN_TTL_MINUTES = 5

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

def new_reset_token():
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
    ).isoformat(timespec="seconds")
    return token, expires_at

def send_reset_email(email, token):
    reset_url = f"{PUBLIC_BASE_URL}/student-4/reset-password.html?token={quote(token)}"
    body = (
        "Hi,\n\n"
        "We received a request to reset your NextStop password. Click the link below to choose a new one.\n\n"
        f"{reset_url}\n\n"
        f"This link can only be used once and expires in {RESET_TOKEN_TTL_MINUTES} minutes.\n"
        "If you didn't request this, you can safely ignore this email."
    )
    message = MIMEText(body)
    message["Subject"] = "Reset your NextStop password"
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

def destination_row(destination):
    detail_url = f"/api/student-4/guides/{destination['id']}"
    return (
        f"<a href='#' class='guide-row' hx-get='{detail_url}' hx-target='#guides-results' hx-swap='innerHTML'>"
        f"<span class='guide-row__name'>{escape(destination['city'])}, {escape(destination['country'])}</span>"
        f"<span class='guide-row__meta'>{escape(destination['region'])}</span>"
        "<span class='guide-row__chevron' aria-hidden='true'>&rsaquo;</span>"
        "</a>"
    )

def destinations_table(destinations, query):
    if not destinations:
        message = f"No cities or countries match \"{query}\"." if query else "No destinations available."
        return f"<p class='result-empty'>{escape(message)}</p>"

    by_country = {}
    for destination in destinations:
        by_country.setdefault(destination["country"], []).append(destination)

    groups = "".join(
        f"<div class='guide-group'><h4 class='guide-group__title'>{escape(country)}</h4>"
        f"<div class='guide-list'>{''.join(destination_row(d) for d in rows)}</div></div>"
        for country, rows in sorted(by_country.items())
    )
    return f"<div class='guide-groups'>{groups}</div>"

def guide_section(title, body, section_id=""):
    # transportation and visa keep an id because their tabs swap the whole section.
    id_attr = f" id='{section_id}'" if section_id else ""
    return (
        f"<section class='guide-section'{id_attr}>"
        f"<h4 class='guide-section__title'>{escape(title)}</h4>{body}</section>"
    )

def guide_tabs(buttons):
    return f"<div class='guide-tabs' role='group'>{buttons}</div>"

def guide_tab(label, url, target, active):
    pressed = "true" if active else "false"
    css = "chip is-active" if active else "chip"
    return (
        f"<button type='button' class='{css}' aria-pressed='{pressed}' hx-get='{url}' "
        f"hx-target='#{target}' hx-swap='outerHTML'>{escape(label)}</button>"
    )

def currency_subsection(destination_id, info):
    if info is None:
        return guide_section("Currency", "<p class='muted'>No currency information yet.</p>")

    body = (
        f"<p><span class='pill pill-planned'>{escape(info['currency_code'])}</span>"
        f"{escape(info['currency_name'])}</p>"
        f"<p>{escape(info['exchange_tips'])}</p>"
        + live_rates_placeholder(destination_id)
    )
    return guide_section("Currency", body)

TRANSPORT_TYPE_LABELS = {
    "flights": "Flights",
    "metro": "Metro",
    "train": "Train",
    "taxi": "Taxi",
    "rental": "Rental",
}

# Flights are the only transport mode this app can actually book (through
# student-5, Bookings & Budget), and only for cities student-5 lists. The
# seed marks those rows bookable.
FLIGHT_BOOKING_URL = "/student-5/#search"

def transportation_section(destination_id, items, active_type):
    if not items:
        return guide_section(
            "Transportation", "<p class='muted'>No transportation information yet.</p>", "transportation-section"
        )

    active = active_type if any(item["type"] == active_type for item in items) else items[0]["type"]
    active_item = next(item for item in items if item["type"] == active)

    tabs = guide_tabs("".join(
        guide_tab(
            TRANSPORT_TYPE_LABELS.get(item["type"], item["type"].title()),
            f"/api/student-4/guides/{destination_id}/transportation?type={item['type']}",
            "transportation-section",
            item["type"] == active,
        )
        for item in items
    ))

    book_button = ""
    if active == "flights" and active_item.get("bookable"):
        book_button = f"<a class='btn-sm guide-action' href='{FLIGHT_BOOKING_URL}'>Book flights</a>"

    body = (
        tabs
        + f"<p>{escape(active_item['description'])}</p>"
        + f"<p class='muted'>{escape(active_item['tips'])}</p>"
        + book_button
    )
    return guide_section("Transportation", body, "transportation-section")

def visa_section(destination_id, items, active_nationality):
    if not items:
        return guide_section("Visa", "<p class='muted'>No visa information yet.</p>", "visa-section")

    active = active_nationality if any(item["nationality"] == active_nationality for item in items) else None

    tabs = guide_tabs("".join(
        guide_tab(
            item["nationality"],
            f"/api/student-4/guides/{destination_id}/visa?nationality={quote(item['nationality'])}",
            "visa-section",
            item["nationality"] == active,
        )
        for item in items
    ))

    if active is None:
        body = "<p class='muted'>Select your nationality to see visa requirements for this destination.</p>"
    else:
        active_item = next(item for item in items if item["nationality"] == active)
        body = (
            f"<p><span class='pill pill-planned'>{escape(active_item['requirement_type'])}</span></p>"
            f"<p>{escape(active_item['notes'])}</p>"
        )

    return guide_section("Visa", tabs + body, "visa-section")

def default_weather_month(items, timezone_name):
    current_month = local_month(timezone_name)
    if any(item["month"] == current_month for item in items):
        return current_month
    return items[0]["month"]

def weather_months(destination_id, items, active_month, timezone_name):
    # The month tabs swap only this block, so the live weather above is not reloaded.
    if not items:
        return "<div id='weather-months'><p class='muted'>No typical weather information yet.</p></div>"

    if not any(item["month"] == active_month for item in items):
        active_month = default_weather_month(items, timezone_name)
    active_item = next(item for item in items if item["month"] == active_month)

    tabs = guide_tabs("".join(
        guide_tab(
            item["month"][:3],
            f"/api/student-4/guides/{destination_id}/weather?month={quote(item['month'])}",
            "weather-months",
            item["month"] == active_month,
        )
        for item in items
    ))

    return (
        "<div id='weather-months'>"
        "<p class='wx-title'>Typical conditions by month</p>"
        + tabs
        + f"<p>The average daytime high in {escape(active_item['month'])} is about "
        f"<strong>{active_item['avg_temp']:g}°C</strong>, with around "
        f"<strong>{active_item['rainfall']:g}mm</strong> of rainfall.</p>"
        + f"<p class='muted'>{escape(active_item['best_visit_time'])}</p>"
        + "</div>"
    )

def weather_section(destination_id, items, timezone_name):
    body = live_weather_placeholder(destination_id) + weather_months(destination_id, items, None, timezone_name)
    return guide_section("Weather", body)

def safety_subsection(info):
    if info is None:
        return guide_section("Safety", "<p class='muted'>No safety information yet.</p>")

    body = (
        f"<p><span class='pill pill-booked'>{escape(info['safety_level'])}</span></p>"
        f"<p>{escape(info['tips'])}</p>"
    )
    return guide_section("Safety", body)

def destination_detail(destination, currency, transportation, visa, weather, safety):
    head = (
        "<div class='guide-head'>"
        "<a href='#' class='back-link' hx-get='/api/student-4/guides' hx-target='#guides-results' "
        "hx-swap='innerHTML'><span aria-hidden='true'>&larr;</span> View all</a>"
        f"<h3>{escape(destination['city'])}, {escape(destination['country'])}</h3>"
        f"<p class='muted'>{escape(destination['region'])}</p>"
        "</div>"
    )
    return (
        head
        + "<div class='guide-grid'>"
        + currency_subsection(destination["id"], currency)
        + transportation_section(destination["id"], transportation, None)
        + visa_section(destination["id"], visa, None)
        + weather_section(destination["id"], weather, destination.get("timezone"))
        + safety_subsection(safety)
        + "</div>"
    )

@app.get("/health")
def health():
    return jsonify({"service": "student-4-api", "status": "running"})

@app.get("/guides")
def list_guides():
    query = (request.args.get("query") or "").strip()
    try:
        response = requests.get(f"{DB_SERVICE_URL}/destinations", params={"query": query}, timeout=5)
        response.raise_for_status()
        return destinations_table(response.json(), query), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

@app.get("/guides/<int:destination_id>")
def guide_detail(destination_id):
    try:
        destination_response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}", timeout=5)
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    if destination_response.status_code == 404:
        return error_fragment("This destination could not be found."), 404
    if destination_response.status_code != 200:
        return error_fragment(DB_DOWN), 503

    try:
        currency_response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/currency", timeout=5)
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    currency = currency_response.json() if currency_response.status_code == 200 else None

    try:
        transport_response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/transportation", timeout=5)
        transportation = transport_response.json() if transport_response.status_code == 200 else []
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    try:
        visa_response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/visa", timeout=5)
        visa = visa_response.json() if visa_response.status_code == 200 else []
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    try:
        weather_response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/weather", timeout=5)
        weather = weather_response.json() if weather_response.status_code == 200 else []
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    try:
        safety_response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/safety", timeout=5)
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    safety = safety_response.json() if safety_response.status_code == 200 else None

    return destination_detail(destination_response.json(), currency, transportation, visa, weather, safety), 200

@app.get("/guides/<int:destination_id>/transportation")
def guide_transportation(destination_id):
    requested_type = request.args.get("type")
    try:
        response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/transportation", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    return transportation_section(destination_id, response.json(), requested_type), 200

@app.get("/guides/<int:destination_id>/visa")
def guide_visa(destination_id):
    requested_nationality = request.args.get("nationality")
    try:
        response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/visa", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    return visa_section(destination_id, response.json(), requested_nationality), 200

@app.get("/guides/<int:destination_id>/weather")
def guide_weather(destination_id):
    requested_month = request.args.get("month")
    try:
        response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/weather", timeout=5)
        response.raise_for_status()
        # Only needed for the default month when the requested one is not seeded.
        destination_response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}", timeout=5)
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    timezone_name = destination_response.json().get("timezone") if destination_response.status_code == 200 else None
    return weather_months(destination_id, response.json(), requested_month, timezone_name), 200

@app.get("/guides/<int:destination_id>/currency")
def guide_currency(destination_id):
    try:
        response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/currency", timeout=5)
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    if response.status_code == 404:
        return currency_subsection(destination_id, None), 200
    if response.status_code != 200:
        return error_fragment(DB_DOWN), 503

    return currency_subsection(destination_id, response.json()), 200

@app.get("/guides/<int:destination_id>/safety")
def guide_safety(destination_id):
    try:
        response = requests.get(f"{DB_SERVICE_URL}/destinations/{destination_id}/safety", timeout=5)
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503

    if response.status_code == 404:
        return safety_subsection(None), 200
    if response.status_code != 200:
        return error_fragment(DB_DOWN), 503

    return safety_subsection(response.json()), 200

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

@app.post("/auth/logout")
def logout():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing fields: user_id"}), 400

    try:
        response = requests.post(
            f"{SHARED_API_URL}/access-logs/sign-out", json={"user_id": user_id}, timeout=5
        )
        data = response.json()
    except requests.RequestException as exc:
        return jsonify({"error": SHARED_DOWN, "detail": str(exc)[:300]}), 503

    if response.status_code != 200:
        return jsonify(data), response.status_code

    return jsonify(data), 200

@app.get("/auth/status/<int:user_id>")
def auth_status(user_id):
    try:
        response = requests.get(f"{SHARED_API_URL}/access-logs/status/{user_id}", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": SHARED_DOWN, "detail": str(exc)[:300]}), 503

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

RESET_REQUESTED_MESSAGE = (
    f"If that email is registered with us, we've sent a password reset link. "
    f"The link can only be used once and expires in {RESET_TOKEN_TTL_MINUTES} minutes."
)

def issue_reset_email(email):
    # A 404 (no such account) is folded into the same generic response as
    # success below, so the caller can never tell the two apart.
    reset_token, reset_expires_at = new_reset_token()

    try:
        response = requests.post(
            f"{SHARED_API_URL}/users/reset-password/request",
            json={
                "email": email,
                "reset_token": reset_token,
                "reset_expires_at": reset_expires_at,
            },
            timeout=5,
        )
        data = response.json()
    except requests.RequestException as exc:
        return jsonify({"error": SHARED_DOWN, "detail": str(exc)[:300]}), 503

    if response.status_code == 404:
        return jsonify({"requested": True, "message": RESET_REQUESTED_MESSAGE}), 200
    if response.status_code == 429:
        return jsonify(data), 429
    if response.status_code != 200:
        return jsonify({"error": SHARED_DOWN}), 503

    try:
        send_reset_email(email, reset_token)
    except OSError as exc:
        return jsonify({"error": "Could not send the email. Please try again."}), 503

    return jsonify({"requested": True, "message": RESET_REQUESTED_MESSAGE}), 200

@app.post("/auth/forgot-password")
def forgot_password():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()

    if not validate_email(email):
        return jsonify({"error": "Enter a valid email address."}), 400

    return issue_reset_email(email)

@app.post("/auth/forgot-password/resend")
def forgot_password_resend():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()

    if not validate_email(email):
        return jsonify({"error": "Enter a valid email address."}), 400

    return issue_reset_email(email)

@app.get("/auth/reset-password/validate/<token>")
def reset_password_validate(token):
    try:
        response = requests.get(
            f"{SHARED_API_URL}/users/reset-password/validate/{token}", timeout=5
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({"error": SHARED_DOWN, "detail": str(exc)[:300]}), 503

@app.post("/auth/reset-password")
def reset_password():
    payload = request.get_json(silent=True) or {}
    token = payload.get("token") or ""
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or ""

    if not token:
        return jsonify({"error": "Missing reset token."}), 400
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400
    if not validate_password(password):
        return jsonify({"error": "Password must be 8-64 characters and include an "
                                  "uppercase letter, a lowercase letter, a number "
                                  "and a special character."}), 400

    try:
        response = requests.post(
            f"{SHARED_API_URL}/users/reset-password/confirm",
            json={"token": token, "password_hash": generate_password_hash(password)},
            timeout=5,
        )
        data = response.json()
    except requests.RequestException as exc:
        return jsonify({"error": SHARED_DOWN, "detail": str(exc)[:300]}), 503

    if response.status_code != 200:
        return jsonify(data), response.status_code

    return jsonify({"reset": True}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5104)
