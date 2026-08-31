"""Shared access database API.

This service exclusively owns the shared access schema. No other service may
open shared.db directly, every read or write goes through this HTTP API.
"""

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Checked against on a "user not found" login attempt so that hashing a real
# password and hashing this dummy take about the same time either way -
# otherwise the response latency itself would reveal whether an email exists.
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_hex(16))

DATABASE_NAME = "/app/data/shared.db"

TRAVELLER_FIELDS = ("full_name", "email", "home_city", "member_since")
USER_FIELDS = (
    "name",
    "email",
    "password_hash",
    "verification_token",
    "verification_expires_at",
    "created_at",
)

# Resend rate limit: at most 5 resends per window, at least 60s apart, then a
# 10 minute cooldown before the window resets and the same pattern repeats.
RESEND_MIN_INTERVAL_SECONDS = 60
RESEND_MAX_ATTEMPTS = 5
RESEND_BLOCK_SECONDS = 600

def now_utc():
    return datetime.now(timezone.utc)

def parse_ts(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/health")
def health():
    return jsonify({"service": "shared-db", "status": "running"})

@app.get("/travellers")
def list_travellers():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM travellers ORDER BY traveller_id"
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.get("/travellers/<int:traveller_id>")
def get_traveller(traveller_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM travellers WHERE traveller_id = ?", (traveller_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Traveller not found"}), 404

    return jsonify(dict(row))

@app.post("/travellers")
def create_traveller():
    payload = request.get_json(silent=True) or {}
    missing = [field for field in TRAVELLER_FIELDS if not payload.get(field)]

    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO travellers (full_name, email, home_city, member_since)
            VALUES (?, ?, ?, ?)
            """,
            tuple(payload[field] for field in TRAVELLER_FIELDS),
        )
        conn.commit()
        traveller_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "A traveller with that email already exists"}), 409
    conn.close()

    return jsonify({"traveller_id": traveller_id}), 201

@app.delete("/travellers/<int:traveller_id>")
def delete_traveller(traveller_id):
    conn = get_db_connection()
    cursor = conn.execute(
        "DELETE FROM travellers WHERE traveller_id = ?", (traveller_id,)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if not deleted:
        return jsonify({"error": "Traveller not found"}), 404

    return jsonify({"deleted": traveller_id})

# Users & access logs
def user_public(row):
    """Drop the password hash and verification token before handing a user
    row back to a caller."""
    data = dict(row)
    data.pop("password_hash", None)
    data.pop("verification_token", None)
    return data

@app.get("/users")
def list_users():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([user_public(row) for row in rows])

@app.get("/users/by-email/<path:email>")
def get_user_by_email(email):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user_public(row))

OPTIONAL_USER_FIELDS = {"verification_token", "verification_expires_at"}

@app.post("/users")
def create_user():
    payload = request.get_json(silent=True) or {}
    missing = [
        f for f in USER_FIELDS if f not in OPTIONAL_USER_FIELDS and payload.get(f) in (None, "")
    ]

    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            f"INSERT INTO users ({', '.join(USER_FIELDS)}) "
            f"VALUES ({', '.join('?' for _ in USER_FIELDS)})",
            tuple(payload.get(f) for f in USER_FIELDS),
        )
        conn.execute(
            "UPDATE users SET last_verification_sent_at = ? WHERE id = ?",
            (now_utc().isoformat(timespec="seconds"), cursor.lastrowid),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Email already registered"}), 409

    user_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return jsonify(user_public(row)), 201

@app.post("/users/verify/<token>")
def verify_user(token):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE verification_token = ?", (token,)
    ).fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "Invalid or already-used verification link"}), 404

    expires_at = parse_ts(row["verification_expires_at"])
    if expires_at and now_utc() > expires_at:
        conn.execute(
            "UPDATE users SET verification_token = NULL WHERE id = ?", (row["id"],)
        )
        conn.commit()
        conn.close()
        return jsonify({"error": "This verification link has expired"}), 410

    conn.execute(
        "UPDATE users SET is_validated = 1, verification_token = NULL WHERE id = ?",
        (row["id"],),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
    conn.close()

    return jsonify(user_public(updated))

@app.post("/users/authenticate")
def authenticate_user():
    """Check email/password server-side so the hash never leaves shared-db.

    Always returns the same generic 401 for "no such user" and "wrong
    password", only once the password is confirmed correct do we reveal
    whether the account still needs verifying, so a wrong password can never
    be used to probe which emails are registered.
    """
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    invalid_response = jsonify({"error": "Invalid email or password."}), 401

    if not email or not password:
        return invalid_response

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if row is None:
        check_password_hash(DUMMY_PASSWORD_HASH, password)
        return invalid_response

    if not check_password_hash(row["password_hash"], password):
        return invalid_response

    if not row["is_validated"]:
        return jsonify({
            "error": "Please verify your email before signing in.",
            "error_code": "email_not_verified",
        }), 403

    return jsonify(user_public(row))

@app.post("/access-logs")
def create_access_log():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing fields: user_id"}), 400

    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO access_logs (user_id, sign_in_at, in_session)
        VALUES (?, ?, 1)
        """,
        (user_id, now_utc().isoformat(timespec="seconds")),
    )
    conn.commit()
    log_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM access_logs WHERE id = ?", (log_id,)).fetchone()
    conn.close()

    return jsonify(dict(row)), 201

@app.post("/access-logs/sign-out")
def sign_out():
    """Close a user's open session: stamp sign_out_at and clear in_session
    on their most recent access_logs row."""
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing fields: user_id"}), 400

    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM access_logs WHERE user_id = ? AND in_session = 1 "
        "ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "No open session for this user"}), 404

    sign_out_at = now_utc().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE access_logs SET sign_out_at = ?, in_session = 0 WHERE id = ?",
        (sign_out_at, row["id"]),
    )
    conn.commit()
    updated = conn.execute(
        "SELECT * FROM access_logs WHERE id = ?", (row["id"],)
    ).fetchone()
    conn.close()

    return jsonify(dict(updated))

@app.get("/access-logs/status/<int:user_id>")
def session_status(user_id):
    """Whether a user is currently signed in, for any feature to check."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM access_logs WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"user_id": user_id, "is_valid": False, "last_logout": None})

    return jsonify({
        "user_id": user_id,
        "is_valid": bool(row["in_session"]),
        "last_logout": row["sign_out_at"],
    })

@app.post("/users/verification/resend")
def resend_verification():
    """Issue a fresh verification token for an unverified user, enforcing:
    - at least 60s between sends
    - at most 5 sends per window
    - a 10 minute cooldown once the window is exhausted, after which the
      window resets and the same 5-then-cooldown pattern repeats

    The caller (student-4-api) generates the token itself and only sends the
    email once this endpoint reports success.
    """
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    token = payload.get("verification_token")
    expires_at = payload.get("verification_expires_at")

    if not email or not token or not expires_at:
        return jsonify({"error": "Missing fields"}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    if row["is_validated"]:
        conn.close()
        return jsonify({"error": "This account is already verified."}), 400

    now = now_utc()
    blocked_until = parse_ts(row["verification_blocked_until"])

    if blocked_until and now < blocked_until:
        conn.close()
        remaining = int((blocked_until - now).total_seconds())
        return jsonify({
            "error": "Too many attempts. Please wait before trying again.",
            "retry_after_seconds": remaining,
        }), 429

    resend_count = row["verification_resend_count"] or 0
    if blocked_until and now >= blocked_until:
        resend_count = 0

    last_sent = parse_ts(row["last_verification_sent_at"])
    if last_sent:
        elapsed = (now - last_sent).total_seconds()
        if elapsed < RESEND_MIN_INTERVAL_SECONDS:
            conn.close()
            remaining = int(RESEND_MIN_INTERVAL_SECONDS - elapsed) + 1
            return jsonify({
                "error": "Please wait before requesting another email.",
                "retry_after_seconds": remaining,
            }), 429

    if resend_count >= RESEND_MAX_ATTEMPTS:
        new_blocked_until = now + timedelta(seconds=RESEND_BLOCK_SECONDS)
        conn.execute(
            "UPDATE users SET verification_resend_count = 0, verification_blocked_until = ? "
            "WHERE id = ?",
            (new_blocked_until.isoformat(timespec="seconds"), row["id"]),
        )
        conn.commit()
        conn.close()
        return jsonify({
            "error": "Too many attempts. Please wait before trying again.",
            "retry_after_seconds": RESEND_BLOCK_SECONDS,
        }), 429

    conn.execute(
        """
        UPDATE users
        SET verification_token = ?,
            verification_expires_at = ?,
            last_verification_sent_at = ?,
            verification_resend_count = ?,
            verification_blocked_until = NULL
        WHERE id = ?
        """,
        (token, expires_at, now.isoformat(timespec="seconds"), resend_count + 1, row["id"]),
    )
    conn.commit()
    conn.close()

    return jsonify({"resent": True, "resend_count": resend_count + 1})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5200)
