"""
Deterministic smoke test for student-4 (Account & Dashboard).

Exercises the real sign-up and email verification flow end to end through
student-4-api, shared-api/shared-db (which own `users`/`access_logs`, see
docs/technical-report.md 2.7 for why) and Mailpit (the local dev SMTP
catcher):

    docker compose up -d student-4-db student-4-api shared-api shared-db mailpit
    python3 student-4/tests/smoke_test.py

Each run registers freshly-randomised emails, so re-running the script never
collides with a previous run's accounts - there is deliberately no
account-delete endpoint to clean up after itself with (see 2.6, R4-6).

Override the target host/port with STUDENT4_API_URL / STUDENT4_MAILPIT_URL
if the services are not on their default ports.
"""

import os
import re
import sys
import time
import uuid

import requests

API_BASE = os.getenv("STUDENT4_API_URL", "http://localhost:5104")
MAILPIT_BASE = os.getenv("STUDENT4_MAILPIT_URL", "http://localhost:8025")

PASSWORD = "Str0ng!Pass1"


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


def run_checks():
    status, _ = _call("GET", f"{API_BASE}/health")
    expect(status == 200, "GET /health returns 200")

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

    # Accounts listing
    status, response = _call("GET", f"{API_BASE}/users")
    expect(status == 200, "GET /users returns 200")
    expect(email in response.text, "the new account appears in the accounts fragment")

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


def main():
    print("Smoke test: student-4 sign-up & email verification")
    try:
        run_checks()
    except SmokeFailure as failure:
        print(f"\nFAIL: {failure}")
        return 1
    print("\nstudent-4 sign-up & email verification passed all checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
