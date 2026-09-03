"""
Deterministic smoke test for student-4 (Account & Dashboard).

Exercises the real sign-up, email verification and sign-in flow end to end
through student-4-api, shared-api/shared-db (which own `users`/`access_logs`,
see docs/technical-report.md 2.7 for why) and Mailpit (the local dev SMTP
catcher), plus the Travel Guides destination search backed by student-4-db:

    docker compose up -d student-4-db student-4-api shared-api shared-db mailpit
    python3 student-4/tests/smoke_test.py

Each run registers freshly-randomised emails, so re-running the script never
collides with a previous run's accounts, there is deliberately no
account-delete endpoint to clean up after itself with.

Checks that the landing page and the shared home page load the sign in
guard (student-4/frontend/templates/index.html and shared/js/auth-guard.js),
that the sign-up, sign-in and verify-pending pages stay reachable without
a session, and that logout.html is actually served once user click sign out button.
"""

import os
import re
import sys
import time
import uuid

import requests

API_BASE = os.getenv("STUDENT4_API_URL", "http://localhost:5104")
MAILPIT_BASE = os.getenv("STUDENT4_MAILPIT_URL", "http://localhost:8025")
FRONTEND_BASE = os.getenv("STUDENT4_FRONTEND_URL", "http://localhost:8084")
SHARED_FRONTEND_BASE = os.getenv("SHARED_FRONTEND_URL", "http://localhost:8080")

PASSWORD = "Str0ng!Pass1"
SEED_PASSWORD = "Password123!"


class SmokeFailure(Exception):
    pass


def _call(method, url, timeout=5, **kwargs):
    try:
        response = requests.request(method, url, timeout=timeout, **kwargs)
        return response.status_code, response
    except requests.RequestException as exc:
        raise SmokeFailure(f"{method} {url} did not connect: {exc}") from exc


def expect(condition, message):
    if not condition:
        raise SmokeFailure(message)
    print(f"  ok  {message}")


def unique_email(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def register(email, password=PASSWORD, terms_accepted=True, name="Smoke Test"):
    payload = {"name": name, "email": email, "password": password}
    if terms_accepted is not None:
        payload["terms_accepted"] = terms_accepted
    return _call("POST", f"{API_BASE}/auth/register", json=payload)


def login(email, password):
    return _call("POST", f"{API_BASE}/auth/login", json={"email": email, "password": password})


def logout(user_id):
    return _call("POST", f"{API_BASE}/auth/logout", json={"user_id": user_id})


def session_status(user_id):
    return _call("GET", f"{API_BASE}/auth/status/{user_id}")


def mailpit_message_count(email):
    status, response = _call(
        "GET", f"{MAILPIT_BASE}/api/v1/search", params={"query": f"to:{email}"}
    )
    return response.json().get("messages_count", 0) if status == 200 else None


def find_verification_link(email, attempts=10, delay=1.0):
    """Poll Mailpit for the verification email and pull the link out of it.

    Mailpit delivery can lag a moment behind the HTTP response that
    triggered it, so this polls rather than checking once.
    """
    for _ in range(attempts):
        status, response = _call("GET", f"{MAILPIT_BASE}/api/v1/messages")
        if status == 200:
            for message in response.json().get("messages", []):
                if message["To"][0]["Address"] == email:
                    status, detail = _call(
                        "GET", f"{MAILPIT_BASE}/api/v1/message/{message['ID']}"
                    )
                    if status == 200:
                        match = re.search(
                            r"http://\S+/auth/verify/\S+", detail.json()["Text"]
                        )
                        if match:
                            return match.group()
        time.sleep(delay)
    return None


def _get_page(url):
    try:
        return requests.get(url, timeout=5)
    except requests.RequestException:
        return None


def run_frontend_guard_checks():
    """Confirm the sign in gate is wired into the protected pages.

    Cannot run the page's own JavaScript here, so this checks what requests
    already checks elsewhere in this file: the response text carries the
    markers the guard needs on protected pages.
    """
    landing = _get_page(f"{FRONTEND_BASE}/")
    if landing is None:
        print("  skip  student-4-frontend is not running, skipping guard checks")
        return

    expect(landing.status_code == 200, "student-4 landing page (index.html) is served")
    expect(
        "verifySession" in landing.text,
        "landing page calls verifySession before showing its content",
    )

    for page in ("signin.html", "signup.html", "verify-pending.html"):
        response = _get_page(f"{FRONTEND_BASE}/{page}")
        expect(response.status_code == 200, f"{page} is served without a session")

    logout_page = _get_page(f"{FRONTEND_BASE}/logout.html")
    expect(logout_page.status_code == 200, "logout.html is served (not just index.html's fallback)")
    expect(
        "justLoggedOut" in logout_page.text,
        "logout.html gates its content behind the one-time sign-out flag",
    )

    shared_home = _get_page(f"{SHARED_FRONTEND_BASE}/")
    if shared_home is None:
        print("  skip  shared-frontend is not running, skipping the shared home page check")
        return

    expect(shared_home.status_code == 200, "shared home page is served")
    expect(
        "auth-guard.js" in shared_home.text,
        "shared home page loads the shared session guard",
    )


def run_checks():
    status, _ = _call("GET", f"{API_BASE}/health")
    expect(status == 200, "GET /health returns 200")

    # Seed data baked into student-4-db's init_db.py, checked here so a build
    # missing it fails CI instead of only showing up on one machine.
    status, response = _call("GET", f"{API_BASE}/guides")
    expect(status == 200, "GET /guides returns 200")
    for city in ("Sydney", "Melbourne", "Perth", "Hobart"):
        expect(city in response.text, f"seeded destination {city} is present")

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Sydney"})
    expect(status == 200, "GET /guides?query=Sydney returns 200")
    expect("Sydney" in response.text, "searching by city returns a match")
    expect("Melbourne" not in response.text, "searching by city excludes other cities")

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Australia"})
    expect(status == 200, "GET /guides?query=Australia returns 200")
    expect("Sydney" in response.text, "searching by country returns its cities")

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Nowhereville"})
    expect(status == 200, "GET /guides?query=Nowhereville returns 200")
    expect(
        "No cities or countries match" in response.text,
        "an unmatched search shows the not-found placeholder",
    )

    status, response = login("student1@example.com", SEED_PASSWORD)
    expect(status == 200, "seeded student1 can sign in")
    logout(response.json()["id"])

    status, response = login("traveller6@example.com", SEED_PASSWORD)
    expect(status == 403, "seeded traveller6 is pending verification")

    email = unique_email("smoke")

    # Validation
    status, response = register(email, terms_accepted=None)
    expect(status == 400, "POST /auth/register without terms_accepted returns 400")
    expect(
        "Terms and Conditions" in response.json().get("error", ""),
        "error message names the T&C requirement",
    )

    status, response = register(email, password="weak")
    expect(status == 400, "POST /auth/register with a weak password returns 400")

    status, response = register("not-an-email", name="Smoke Test")
    expect(status == 400, "POST /auth/register with an invalid email returns 400")

    # Registration
    status, response = register(email)
    expect(status == 201, "POST /auth/register with valid data returns 201")
    created = response.json()
    expect(created.get("email") == email, "created account has the requested email")
    expect(created.get("is_validated") == 0, "created account starts unverified")
    expect(
        "verification_token" not in created and "password_hash" not in created,
        "the response never leaks the token or the password hash",
    )

    status, response = register(email)
    expect(status == 409, "registering the same email again returns 409")

    # Email verification
    link = find_verification_link(email)
    expect(link is not None, "verification email arrives in Mailpit with a link")

    status, response = _call("GET", link)
    expect(status == 200, "visiting the verification link returns 200")
    expect("Email verified" in response.text, "the link confirms verification")

    status, response = _call("GET", link)
    expect(status == 404, "reusing the same (now-spent) link returns 404")

    status, response = _call("POST", f"{API_BASE}/auth/resend", json={"email": email})
    expect(status == 400, "resending for an already-verified account returns 400")

    # Resend rate limit, on a second, still-unverified account
    resend_email = unique_email("smoke-resend")
    status, _ = register(resend_email)
    expect(status == 201, "second account for resend testing registers successfully")

    status, response = _call(
        "POST", f"{API_BASE}/auth/resend", json={"email": resend_email}
    )
    expect(status == 429, "resending within 60s of registering returns 429")
    expect(
        response.json().get("retry_after_seconds", 0) > 0,
        "429 response names how long to wait",
    )

    # Sign-in
    status, response = login(email, "WrongPassword1!")
    expect(status == 401, "POST /auth/login with the wrong password returns 401")
    wrong_password_error = response.json().get("error")
    expect(
        wrong_password_error == "Invalid email or password.",
        "wrong-password error message is the generic one",
    )

    status, response = login(unique_email("smoke-no-account"), PASSWORD)
    expect(status == 401, "POST /auth/login for an email with no account returns 401")
    expect(
        response.json().get("error") == wrong_password_error,
        "unknown-email error is identical to wrong-password (no account enumeration)",
    )

    sent_before = mailpit_message_count(resend_email)
    status, response = login(resend_email, PASSWORD)
    expect(status == 403, "POST /auth/login with the correct password on an unverified account returns 403")
    expect(
        response.json().get("error_code") == "email_not_verified",
        "403 response names the email_not_verified error code",
    )
    sent_after = mailpit_message_count(resend_email)
    expect(
        sent_after == sent_before,
        "signing in to an unverified account within the resend cooldown does not send a duplicate email",
    )

    status, response = login(email, PASSWORD)
    expect(status == 200, "POST /auth/login with the correct password on a verified account returns 200")
    signed_in = response.json()
    expect(signed_in.get("email") == email, "login response returns the signed-in user")
    expect(
        "password_hash" not in signed_in and "verification_token" not in signed_in,
        "login response never leaks the password hash or verification token",
    )

    # Sign-out and session status, the contract other features use to check
    # whether a user is signed in (docs/ADR-001-service-boundaries.md,
    # Decision 6)
    user_id = signed_in["id"]

    status, response = session_status(user_id)
    expect(status == 200, "GET /auth/status/<id> returns 200")
    expect(response.json().get("is_valid") is True, "session is valid right after login")
    expect(response.json().get("last_logout") is None, "no last_logout recorded yet")

    status, response = _call("POST", f"{API_BASE}/auth/logout", json={})
    expect(status == 400, "POST /auth/logout without a user_id returns 400")

    status, response = logout(user_id)
    expect(status == 200, "POST /auth/logout for the signed-in user returns 200")
    expect(response.json().get("in_session") == 0, "logout response reports in_session = 0")
    expect(response.json().get("sign_out_at") is not None, "logout response stamps sign_out_at")

    status, response = session_status(user_id)
    expect(status == 200, "GET /auth/status/<id> returns 200 after logout")
    expect(response.json().get("is_valid") is False, "session is invalid after logout")
    expect(response.json().get("last_logout") is not None, "last_logout is now recorded")

    status, response = logout(user_id)
    expect(status == 404, "logging out again with no open session returns 404")

    status, response = session_status(999999999)
    expect(status == 200, "GET /auth/status/<id> for an unknown id still returns 200")
    expect(
        response.json().get("is_valid") is False,
        "an unknown user id is reported as not signed in, not an error",
    )

    # Frontend sign in gate, best effort since the frontend containers are
    # optional for this script, see the module docstring.
    run_frontend_guard_checks()


def main():
    print("Smoke test: student-4 sign-up, email verification & sign-in")
    try:
        run_checks()
    except SmokeFailure as failure:
        print(f"\nFAIL: {failure}")
        return 1
    print("\nstudent-4 sign-up, email verification & sign-in passed all checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())