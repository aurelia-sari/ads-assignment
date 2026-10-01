"""
Deterministic smoke test for student-4 (Account & Dashboard).

Exercises the real sign-up, email verification, forgot/reset password and
sign-in flow end to end through student-4-api, shared-api/shared-db (which
own `users`/`access_logs`, see docs/technical-report.md 2.7 for why) and
Mailpit (the local dev SMTP catcher), plus the Travel Guides destination
search backed by student-4-db and the AI Assistant tab:

    ./scripts/ai_services.sh up    # optional, AI-Mode, MCP and RAG run on the host
    docker compose up -d student-4-db student-4-api shared-api shared-db mailpit
    python3 student-4/tests/smoke_test.py

Each run registers freshly-randomised emails, so re-running the script never
collides with a previous run's accounts, there is deliberately no
account-delete endpoint to clean up after itself with.

Checks that the landing page and the shared home page load the sign in
guard (student-4/frontend/templates/index.html and shared/js/auth-guard.js),
that the sign-up, sign-in, verify-pending, forgot-password,
forgot-password-pending and reset-password pages stay reachable without a
session, and that logout.html is actually served once user click sign out button.

The AI Assistant checks split into two groups. The intent classification and
redirect checks never call the model, so they always run. The checks that
need a real answer from the model (grounded weather and transport questions,
and the session history built from them) are skipped when ai-mode is not
reachable, the same way run_frontend_guard_checks skips when the frontend
containers are not running.

The Release 1 MCP and RAG checks follow whatever GET /ai-tools/status
reports. In CI both are disabled, so the disabled response is asserted.
Locally with the host AI services running, the live tool call, a boundary
refusal and the insufficient-context reply are asserted instead.
"""

import os
import re
import sys
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

API_BASE = os.getenv("STUDENT4_API_URL", "http://localhost:5104")
MAILPIT_BASE = os.getenv("STUDENT4_MAILPIT_URL", "http://localhost:8025")
FRONTEND_BASE = os.getenv("STUDENT4_FRONTEND_URL", "http://localhost:8084")
SHARED_FRONTEND_BASE = os.getenv("SHARED_FRONTEND_URL", "http://localhost:8080")
AI_MODE_BASE = os.getenv("AI_MODE_URL", "http://localhost:5300")

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


def request_reset(email):
    return _call("POST", f"{API_BASE}/auth/forgot-password", json={"email": email})


def resend_reset(email):
    return _call("POST", f"{API_BASE}/auth/forgot-password/resend", json={"email": email})


def validate_reset_token(token):
    return _call("GET", f"{API_BASE}/auth/reset-password/validate/{token}")


def confirm_reset(token, password, confirm_password=None):
    return _call(
        "POST",
        f"{API_BASE}/auth/reset-password",
        json={
            "token": token,
            "password": password,
            "confirm_password": password if confirm_password is None else confirm_password,
        },
    )


def find_reset_token(email, attempts=10, delay=1.0):
    """Poll Mailpit for the reset email and pull the token out of its link,
    the same way find_verification_link polls for the verification email."""
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
                            r"reset-password\.html\?token=([A-Za-z0-9_-]+)",
                            detail.json()["Text"],
                        )
                        if match:
                            return match.group(1)
        time.sleep(delay)
    return None


def _get_page(url):
    try:
        return requests.get(url, timeout=5)
    except requests.RequestException:
        return None


def ai_mode_reachable():
    """ai-mode's own /health returns 200 as long as its Flask process is up,
    even when the Ollama it wraps is not reachable. /model actually calls Ollama,
    so that is the one that tells us whether a real answer is possible.
    """
    try:
        response = requests.get(f"{AI_MODE_BASE}/model", timeout=10)
        return response.status_code == 200 and response.json().get("reachable") is True
    except requests.RequestException:
        return False


def run_forgot_password_checks(email):
    """Checks the forgot / reset password flow, mirroring the shape of the
    email verification checks above: a generic response whether or not the
    email is registered, a rate-limited resend, a single-use token, and a
    server-validated new password.
    """
    status, response = request_reset("not-an-email")
    expect(status == 400, "POST /auth/forgot-password with an invalid email returns 400")

    unknown_email = unique_email("smoke-reset-unknown")
    status, unknown_response = request_reset(unknown_email)
    expect(status == 200, "POST /auth/forgot-password for an unregistered email returns 200")

    status, known_response = request_reset(email)
    expect(status == 200, "POST /auth/forgot-password for a registered email returns 200")
    expect(
        known_response.json() == unknown_response.json(),
        "the response is identical whether or not the email is registered",
    )

    token = find_reset_token(email)
    expect(token is not None, "reset email arrives in Mailpit with a link")

    status, response = validate_reset_token(token)
    expect(status == 200, "GET /auth/reset-password/validate/<token> returns 200 for a fresh token")
    expect(response.json().get("email") == email, "the validate response names the right account")

    status, response = validate_reset_token("not-a-real-token")
    expect(status == 404, "GET /auth/reset-password/validate/<token> returns 404 for an unknown token")

    status, response = confirm_reset(token, "N3wStr0ng!Pass", confirm_password="Different1!")
    expect(status == 400, "POST /auth/reset-password with mismatched passwords returns 400")

    status, response = confirm_reset(token, "weak")
    expect(status == 400, "POST /auth/reset-password with a weak password returns 400")

    status, response = confirm_reset(token, "N3wStr0ng!Pass")
    expect(status == 200, "POST /auth/reset-password with a valid token and password returns 200")
    expect(response.json().get("reset") is True, "reset response confirms the reset")

    status, response = confirm_reset(token, "AnotherPass1!")
    expect(status == 404, "reusing the same (now-spent) reset token returns 404")

    status, response = login(email, PASSWORD)
    expect(status == 401, "signing in with the old password after a reset returns 401")

    status, response = login(email, "N3wStr0ng!Pass")
    expect(status == 200, "signing in with the new password after a reset returns 200")
    logout(response.json()["id"])

    # Resend rate limit, on a second account
    resend_email = unique_email("smoke-reset-resend")
    status, _ = register(resend_email)
    expect(status == 201, "second account for reset resend testing registers successfully")

    status, _ = request_reset(resend_email)
    expect(status == 200, "first reset request for the resend account returns 200")

    status, response = resend_reset(resend_email)
    expect(status == 429, "resending within 60s of the first request returns 429")
    expect(
        response.json().get("retry_after_seconds", 0) > 0,
        "429 response names how long to wait",
    )


def ai_guide_chat(question, user_id=None, session_id=None, timeout=180):
    payload = {"question": question}
    if user_id is not None:
        payload["user_id"] = user_id
    if session_id is not None:
        payload["session_id"] = session_id
    return _call("POST", f"{API_BASE}/ai/guide-chat", json=payload, timeout=timeout)


def run_ai_assistant_checks():
    """Checks the Travel Guides AI Assistant, added alongside the guide
    subsections. Plan and Adapt are pure classification, so the auth gate,
    the redirects and the no city fallback are checked unconditionally.
    Only the guide category answers, which need a real model call, are
    skipped when ai-mode is not running.
    """
    status, response = ai_guide_chat("Is Sydney safe?")
    expect(status == 401, "POST /ai/guide-chat without a user_id returns 401")
    expect("error" in response.json(), "401 response names an error")

    status, response = login("student1@example.com", SEED_PASSWORD)
    expect(status == 200, "student1 signs in for the AI Assistant checks")
    ai_user_id = response.json()["id"]

    status, response = ai_guide_chat("", user_id=ai_user_id)
    expect(status == 400, "POST /ai/guide-chat with an empty question returns 400")

    status, response = ai_guide_chat("Can I book a hotel here?", user_id=ai_user_id)
    expect(status == 200, "a redirect question returns 200 without a session or a city")
    redirect = response.json()
    expect(
        redirect.get("intent") == "other:Bookings & Budget",
        "booking a hotel classifies as another feature, not a guide category",
    )
    expect(
        redirect.get("redirect_path") == "/student-5/#search",
        "the hotel redirect points at student-5's search",
    )
    expect(redirect.get("session_id") is None, "a redirect with no prior session starts none")

    status, response = ai_guide_chat(
        "Can you recommend some good food in Sydney?", user_id=ai_user_id
    )
    expect(status == 200, "a food question returns 200")
    expect(
        response.json().get("intent") == "other:Attractions & Dining",
        "a food question redirects to Attractions & Dining, not student-5",
    )
    expect(
        response.json().get("redirect_path") == "/student-2/",
        "the food redirect points at student-2",
    )

    status, response = ai_guide_chat("What is the capital of France?", user_id=ai_user_id)
    expect(status == 200, "an unrelated question returns 200")
    expect(
        response.json().get("intent") == "unrelated",
        "a question with no guide keyword and no redirect keyword is unrelated",
    )

    status, response = ai_guide_chat("What's the weather like?", user_id=ai_user_id)
    expect(status == 200, "a guide category question with no city returns 200")
    no_city = response.json()
    expect(no_city.get("intent") == "weather", "the topic is still classified without a city")
    expect(no_city.get("adapted") is True, "a missing city is an adapted response")
    expect(no_city.get("session_id") is None, "no session is created when no city is named")
    expect("Tokyo" in no_city.get("answer", ""), "the no city prompt lists the Japanese cities too")

    status, response = ai_guide_chat("How's the weather in Alice Springs?", user_id=ai_user_id)
    unknown = response.json()
    expect(
        "Australia (" in unknown.get("answer", "") and "Japan (" in unknown.get("answer", ""),
        "a city without a guide gets the list of cities that have one",
    )
    expect(unknown.get("session_id") is None, "a city without a guide starts no session")

    status, response = ai_guide_chat("Alice Springs", user_id=ai_user_id)
    expect(
        "Sydney" in response.json().get("answer", ""),
        "a bare place name without a guide also lists the cities that have one",
    )

    status, response = ai_guide_chat("Tokyo", user_id=ai_user_id)
    bare_city = response.json()
    expect(
        bare_city.get("answer", "").startswith("What would you like to know about Tokyo"),
        "a bare city name asks which topic",
    )
    bare_city_session = bare_city.get("session_id")
    expect(bare_city_session is not None, "a bare city name starts a session for that city")

    status, response = ai_guide_chat("How much yen should I carry?", user_id=ai_user_id)
    expect(response.json().get("intent") == "currency", "asking about yen is a currency question")

    status, response = ai_guide_chat("Is the shinkansen worth it?", user_id=ai_user_id)
    expect(response.json().get("intent") == "transport", "asking about the shinkansen is a transport question")

    # Conversions are calculated in code, so these need no model. CI has no
    # live rates, so there the assistant says so instead.
    status, response = ai_guide_chat("How much is 500 AUD to yen?", user_id=ai_user_id)
    answer = response.json().get("answer", "")
    expect(
        answer.startswith("500 AUD is about ") or "Live exchange rates are not available" in answer,
        "a conversion is answered from the live rates, or says they are unavailable",
    )

    status, response = ai_guide_chat("How much is 1000 baht in yen?", user_id=ai_user_id)
    expect(
        response.json().get("answer", "").startswith("Only AUD, JPY, USD, EUR and GBP are available"),
        "an unsupported currency lists the currencies that are available",
    )

    # With AI_MODE_ENABLED=false, as in CI, the guide's figures for the named
    # month are quoted instead of a 503. A 503 is only expected when the flag
    # is on but AI-Mode is not running.
    status, response = ai_guide_chat("How much rain does Cairns get in July?", user_id=ai_user_id)
    if status == 503:
        expect(not ai_mode_reachable(), "only an unreachable AI-Mode gives a 503")
    else:
        month = response.json()
        expect(status == 200 and month.get("intent") == "weather", "a named month weather question returns 200")
        if month.get("answer", "").startswith("Here is what the guide says"):
            expect("36mm" in month["answer"], "the guide's July figures for Cairns are quoted")
        _call("DELETE", f"{API_BASE}/ai/guide-chat/session/{month.get('session_id')}")

    if not ai_mode_reachable():
        _call("DELETE", f"{API_BASE}/ai/guide-chat/session/{bare_city_session}")
        print("  skip  ai-mode is not running, skipping the model-grounded AI Assistant checks")
        return

    status, response = ai_guide_chat(
        "What's the weather like?", user_id=ai_user_id, session_id=bare_city_session
    )
    expect(response.json().get("intent") == "weather", "the follow up topic is classified")
    status, response = _call("GET", f"{API_BASE}/ai/guide-chat/session/{bare_city_session}")
    expect(response.json().get("city") == "Tokyo", "the follow up stays on the city named before")
    _call("DELETE", f"{API_BASE}/ai/guide-chat/session/{bare_city_session}")

    status, response = ai_guide_chat(
        "What is the weather like in Cairns in July?", user_id=ai_user_id
    )
    expect(status == 200, "a grounded weather question returns 200")
    weather = response.json()
    expect(weather.get("intent") == "weather", "the weather question classifies as weather")
    session_id = weather.get("session_id")
    expect(session_id is not None, "a resolved city starts a chat session")

    status, response = ai_guide_chat(
        "Can I get a rental car in Sydney?", user_id=ai_user_id
    )
    expect(status == 200, "a rental car question returns 200")
    rental = response.json()
    expect(rental.get("intent") == "transport", "asking about a rental car is a transport question")
    expect(
        "/student-5" not in rental.get("answer", ""),
        "a rental car question answers from the guide, it does not redirect to student-5",
    )

    status, response = ai_guide_chat(
        "What about the rainfall?", user_id=ai_user_id, session_id=session_id
    )
    expect(status == 200, "a follow up question in the same session returns 200")
    followup = response.json()
    expect(
        followup.get("session_id") == session_id,
        "a follow up with no new city continues the same session",
    )

    status, response = _call("GET", f"{API_BASE}/ai/guide-chat/session/{session_id}")
    expect(status == 200, f"GET /ai/guide-chat/session/{session_id} returns 200")
    session_detail = response.json()
    expect(session_detail.get("city") == "Cairns", "the session's city is Cairns")
    expect(
        len(session_detail.get("messages", [])) >= 4,
        "the session has both questions and both answers recorded",
    )

    status, response = _call("GET", f"{API_BASE}/users/{ai_user_id}/guide-chat-sessions")
    expect(status == 200, f"GET /users/{ai_user_id}/guide-chat-sessions returns 200")
    expect(
        any(session["id"] == session_id for session in response.json()),
        "the session appears in the user's chat session list",
    )

    status, response = _call("DELETE", f"{API_BASE}/ai/guide-chat/session/{session_id}")
    expect(status == 200, f"DELETE /ai/guide-chat/session/{session_id} returns 200")
    expect(response.json().get("deleted") is True, "the delete response confirms deletion")

    status, response = _call("GET", f"{API_BASE}/ai/guide-chat/session/{session_id}")
    expect(status == 404, "the deleted session can no longer be fetched")

    status, response = _call("DELETE", f"{API_BASE}/ai/guide-chat/session/{session_id}")
    expect(status == 404, "deleting an already deleted session returns 404, not an error")

    logout(ai_user_id)


def run_live_rate_checks(sydney_id, tokyo_id):
    """CI sets GUIDES_LIVE_DATA=false, so there the disabled note is checked.
    Locally the real Frankfurter rates are checked, or the unavailable note
    if the internet is down."""
    status, response = _call("GET", f"{API_BASE}/guides/{sydney_id}/currency/live", timeout=30)
    state = response.json().get("status")
    expect(state in ("ok", "disabled", "unavailable"), f"live rates report a known state ({state})")

    if state == "disabled":
        expect(status == 200, "live rates switched off still return 200")
        html = _call(
            "GET", f"{API_BASE}/guides/{sydney_id}/currency/live", headers={"HX-Request": "true"}
        )[1].text
        expect("switched off" in html, "the page says live rates are switched off")
        return

    if state == "unavailable":
        expect(status == 503, "unreachable live rates return 503, not a crash")
        html = _call(
            "GET", f"{API_BASE}/guides/{sydney_id}/currency/live", headers={"HX-Request": "true"}
        )[1].text
        expect("could not be loaded" in html, "the page falls back to a clear note")
        return

    lines = response.json()["lines"]
    expect(any(line.startswith("1 USD = ") and line.endswith(" AUD") for line in lines),
           "Sydney shows the US dollar in Australian dollars")
    expect(any(line.startswith("100 JPY = ") for line in lines), "Sydney shows the yen per 100")

    status, response = _call("GET", f"{API_BASE}/guides/{tokyo_id}/currency/live", timeout=30)
    expect(
        any(line.startswith("1 AUD = ") and line.endswith(" JPY") for line in response.json().get("lines", [])),
        "Tokyo shows the Australian dollar in yen",
    )


def run_live_weather_checks(sydney_id, tokyo_id):
    """Same states as the live rates. The month tab check runs either way,
    since it needs only the seeded data and each city's timezone."""
    status, response = _call("GET", f"{API_BASE}/guides/{tokyo_id}")
    tokyo_month = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%b")
    active = re.findall(r"class='chip is-active'[^>]*hx-target='#weather-months'[^>]*>(\w+)<", response.text)
    expect(active == [tokyo_month], f"Tokyo's weather opens on Tokyo's own month ({tokyo_month})")
    expect(
        f"/guides/{tokyo_id}/weather/live" in response.text,
        "the weather section loads live weather separately, after the guide renders",
    )

    status, response = _call("GET", f"{API_BASE}/guides/{sydney_id}/weather/live", timeout=30)
    state = response.json().get("status")
    expect(state in ("ok", "disabled", "unavailable"), f"live weather reports a known state ({state})")
    html = _call(
        "GET", f"{API_BASE}/guides/{sydney_id}/weather/live", headers={"HX-Request": "true"}
    )[1].text

    if state == "disabled":
        expect(status == 200, "live weather switched off still returns 200")
        expect("switched off" in html, "the page says live weather is switched off")
        return

    if state == "unavailable":
        expect(status == 503, "unreachable live weather returns 503, not a crash")
        expect("could not be loaded" in html, "the page falls back to a clear note")
        return

    body = response.json()
    expect(body["timezone"] == "Australia/Sydney", "Open-Meteo reports Sydney's own timezone")
    expect(body["lines"][0].startswith("Now: ") and "°C" in body["lines"][0], "current conditions are listed")
    expect(len(body["lines"]) == 4, "three forecast days follow the current conditions")
    expect("Now in Sydney" in html and "wx-days" in html, "the page shows current conditions and a forecast")


def run_mcp_rag_checks():
    status, response = _call("GET", f"{API_BASE}/ai-tools/status")
    expect(status == 200, "GET /ai-tools/status returns 200")
    state = response.json()
    expect(
        set(state.values()) <= {"available", "disabled", "unavailable"},
        f"status reports a known state for each server ({state})",
    )

    status, response = _call("POST", f"{API_BASE}/rag/ask", json={"question": ""})
    expect(status == 400, "POST /rag/ask with an empty question returns 400")

    status, response = _call(
        "POST", f"{API_BASE}/mcp/destination-guide", json={"query": "Australia"}, timeout=40
    )
    if state["mcp"] == "disabled":
        expect(status == 200, "MCP disabled, the proxy still returns 200")
        expect(response.json().get("status") == "disabled", "MCP disabled response says disabled")
    elif state["mcp"] == "unavailable":
        expect(status == 503, "MCP unreachable returns 503, not a crash")
        expect(response.json().get("status") == "unavailable", "MCP unreachable response says unavailable")
    else:
        structured = response.json()["result"]["structuredContent"]
        expect(status == 200, "POST /mcp/destination-guide returns 200")
        expect(structured["source"] == "student-4-db", "the MCP tool reads student-4-db")
        expect(structured["row_count"] > 0, "the MCP tool finds Australian destinations")

        status, response = _call(
            "POST", f"{API_BASE}/mcp/destination-guide", json={"query": ""}, timeout=40
        )
        refused = response.json()["result"]
        expect(refused.get("isError") is True, "an empty query is refused by MCP")
        expect(refused.get("boundary") == "schema-checked", "the refusal names the schema-checked boundary")

    # An off-corpus question never reaches the model, so it is fast even when enabled.
    status, response = _call(
        "POST", f"{API_BASE}/rag/ask", json={"question": "What is the capital of Peru?"}, timeout=40
    )
    if state["rag"] == "disabled":
        expect(status == 200, "RAG disabled, the proxy still returns 200")
        expect(response.json().get("status") == "disabled", "RAG disabled response says disabled")
    elif state["rag"] == "unavailable":
        expect(status == 503, "RAG unreachable returns 503, not a crash")
    else:
        body = response.json()
        expect(status == 200, "POST /rag/ask returns 200")
        expect(body.get("grounded") is False, "an off-topic question is not answered")
        expect(body.get("confidence") == "insufficient", "the reply is insufficient context")
        expect(body.get("citations") == [], "an insufficient-context reply cites nothing")


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
    expect(
        "panel-mcp" in landing.text and "panel-rag" in landing.text,
        "landing page has the MCP tools and Ask (grounded) tabs",
    )

    for page in (
        "signin.html",
        "signup.html",
        "verify-pending.html",
        "forgot-password.html",
        "forgot-password-pending.html",
        "reset-password.html",
    ):
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
    for city in ("Sydney", "Melbourne", "Brisbane", "Perth", "Cairns",
                 "Tokyo", "Osaka", "Sapporo", "Kyoto", "Nara"):
        expect(city in response.text, f"seeded destination {city} is present")
    expect("Hobart" not in response.text, "cities removed from the seed are gone")

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Sydney"})
    expect(status == 200, "GET /guides?query=Sydney returns 200")
    expect("Sydney" in response.text, "searching by city returns a match")
    expect("Melbourne" not in response.text, "searching by city excludes other cities")

    match = re.search(r"/guides/(\d+)", response.text)
    expect(match is not None, "the Sydney row links to its guide detail endpoint")
    sydney_id = match.group(1)

    status, response = _call("GET", f"{API_BASE}/guides/{sydney_id}")
    expect(status == 200, f"GET /guides/{sydney_id} returns 200")
    expect("Sydney" in response.text, "the detail view names the city")
    expect("View all" in response.text, "the detail view has a back-to-list link")
    expect("Currency" in response.text, "the detail view has a Currency subheading")
    expect("AUD" in response.text, "the detail view names the Australian Dollar code")
    expect(
        "Cards are accepted almost everywhere. Carry" in response.text,
        "currency copy uses a period, not a semicolon, between sentences",
    )
    expect("—" not in response.text, "guide text does not use an em dash")
    expect("Transportation" in response.text, "the detail view has a Transportation subheading")
    expect("Flights" in response.text, "the detail view lists a Flights transport tab")
    expect(
        "Book flights" in response.text,
        "the default (flights) transport tab shows a booking button",
    )
    expect(
        "/student-5/#search" in response.text,
        "the flights booking button links to student-5's search",
    )

    status, response = _call(
        "GET", f"{API_BASE}/guides/{sydney_id}/transportation", params={"type": "metro"}
    )
    expect(status == 200, "GET /guides/<id>/transportation?type=metro returns 200")
    expect("Metro" in response.text, "the metro tab is shown")
    expect(
        "Book flights" not in response.text,
        "the metro tab does not show a flights booking button",
    )

    status, response = _call("GET", f"{API_BASE}/guides/{sydney_id}")
    expect("Visa" in response.text, "the detail view has a Visa subheading")
    expect("New Zealand" in response.text, "the detail view lists a New Zealand visa tab")
    expect(
        "Select your nationality" in response.text,
        "no nationality is picked by default, so a placeholder is shown instead of a guess",
    )

    status, response = _call(
        "GET", f"{API_BASE}/guides/{sydney_id}/visa", params={"nationality": "New Zealand"}
    )
    expect(status == 200, "GET /guides/<id>/visa?nationality=New Zealand returns 200")
    expect("Visa on arrival" in response.text, "New Zealand's requirement type is shown")
    expect(
        "Select your nationality" not in response.text,
        "picking a nationality replaces the placeholder with its requirement",
    )

    status, response = _call(
        "GET", f"{API_BASE}/guides/{sydney_id}/visa", params={"nationality": "Atlantis"}
    )
    expect(status == 200, "GET /guides/<id>/visa?nationality=<unknown> returns 200")
    expect(
        "Select your nationality" in response.text,
        "an unseeded nationality falls back to the placeholder, not an error",
    )

    status, response = _call("GET", f"{API_BASE}/guides/{sydney_id}")
    expect("Weather" in response.text, "the detail view has a Weather subheading")
    expect("Jan" in response.text, "the detail view lists a January weather tab")
    expect("°C" in response.text, "the default weather tab shows a temperature")
    expect("average daytime high" in response.text, "the weather figure is labelled as a daytime high")

    status, response = _call(
        "GET", f"{API_BASE}/guides/{sydney_id}/weather", params={"month": "July"}
    )
    expect(status == 200, "GET /guides/<id>/weather?month=July returns 200")
    expect("July" in response.text, "the July tab is shown")

    status, response = _call(
        "GET", f"{API_BASE}/guides/{sydney_id}/weather", params={"month": "Notamonth"}
    )
    expect(status == 200, "GET /guides/<id>/weather?month=<invalid> returns 200")
    expect(
        "Notamonth" not in response.text,
        "an invalid month falls back to a real month, not an error",
    )

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Cairns"})
    expect(status == 200, "GET /guides?query=Cairns returns 200")
    match = re.search(r"/guides/(\d+)", response.text)
    expect(match is not None, "the Cairns row links to its guide detail endpoint")
    cairns_id = match.group(1)

    status, response = _call(
        "GET", f"{API_BASE}/guides/{cairns_id}/weather", params={"month": "January"}
    )
    expect(status == 200, f"GET /guides/{cairns_id}/weather?month=January returns 200")
    expect(
        "dry season" in response.text,
        "Cairns's best time to visit note names the dry season",
    )

    status, response = _call("GET", f"{API_BASE}/guides/{sydney_id}")
    expect("Safety" in response.text, "the detail view has a Safety subheading")
    expect(
        "Exercise normal safety precautions" in response.text,
        "the detail view shows Australia's safety level",
    )
    expect(
        "surf conditions and rips" in response.text,
        "the detail view shows Sydney's own safety tips",
    )

    status, response = _call("GET", f"{API_BASE}/guides/{sydney_id}/safety")
    expect(status == 200, f"GET /guides/{sydney_id}/safety returns 200")
    expect("Safety" in response.text, "the safety fragment has a Safety subheading")

    status, response = _call(
        "GET", f"{API_BASE}/guides/{cairns_id}/safety"
    )
    expect(status == 200, f"GET /guides/{cairns_id}/safety returns 200")
    expect(
        "stinger season" in response.text,
        "Cairns has its own safety tips, not Sydney's",
    )

    status, response = _call("GET", f"{API_BASE}/guides/999999999/safety")
    expect(status == 200, "GET /guides/<unknown id>/safety still returns 200")
    expect(
        "No safety information" in response.text,
        "an unknown destination id shows a not-found message, not an error",
    )

    status, response = _call("GET", f"{API_BASE}/guides/{cairns_id}")
    expect("Metro" not in response.text, "Cairns has no metro, so no Metro tab is shown")

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Nara"})
    expect(status == 200, "GET /guides?query=Nara returns 200")
    match = re.search(r"/guides/(\d+)", response.text)
    expect(match is not None, "the Nara row links to its guide detail endpoint")
    nara_id = match.group(1)

    status, response = _call("GET", f"{API_BASE}/guides/{nara_id}")
    expect(status == 200, f"GET /guides/{nara_id} returns 200")
    expect("Metro" not in response.text, "Nara has no metro, so no Metro tab is shown")
    expect("Flights" not in response.text, "Nara has no airport, so no Flights tab is shown")
    expect("Kansai" in response.text, "Nara's default train tab names the nearest airport")
    expect("Book flights" not in response.text, "a city with no flights has no booking button")

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Tokyo"})
    match = re.search(r"/guides/(\d+)", response.text)
    expect(match is not None, "the Tokyo row links to its guide detail endpoint")
    tokyo_id = match.group(1)

    status, response = _call("GET", f"{API_BASE}/guides/{tokyo_id}")
    expect(status == 200, f"GET /guides/{tokyo_id} returns 200")
    expect("JPY" in response.text, "a Japanese city uses the Japanese Yen")
    expect("AUD" not in response.text, "a Japanese city does not show the Australian Dollar")
    expect("Flights" in response.text, "Tokyo has a Flights tab")
    expect(
        "Book flights" not in response.text,
        "student-5 has no flights to Japan, so Tokyo shows no booking button",
    )
    expect("Earthquakes" in response.text, "Tokyo has its own safety tips")

    status, response = _call(
        "GET", f"{API_BASE}/guides/{tokyo_id}/visa", params={"nationality": "Australia"}
    )
    expect("Visa exempt" in response.text, "Australians use Japan's visa rules in Tokyo")
    expect("90 days" in response.text, "the Japan visa note gives the stay length")

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Sapporo"})
    match = re.search(r"/guides/(\d+)", response.text)
    expect(match is not None, "the Sapporo row links to its guide detail endpoint")
    status, response = _call(
        "GET", f"{API_BASE}/guides/{match.group(1)}/weather", params={"month": "January"}
    )
    expect("heavy snow" in response.text, "Sapporo's weather note names the winter snow")

    status, response = _call("GET", f"{API_BASE}/guides/999999999")
    expect(status == 404, "GET /guides/<unknown id> returns 404")

    status, response = _call("GET", f"{API_BASE}/guides/{sydney_id}/currency")
    expect(status == 200, f"GET /guides/{sydney_id}/currency returns 200")
    expect("Currency" in response.text, "currency fragment has a Currency subheading")
    expect("AUD" in response.text, "currency fragment names the Australian Dollar code")
    expect(
        f"/guides/{sydney_id}/currency/live" in response.text,
        "the currency section loads live rates separately, after the guide renders",
    )
    run_live_rate_checks(sydney_id, tokyo_id)
    run_live_weather_checks(sydney_id, tokyo_id)

    status, response = _call("GET", f"{API_BASE}/guides/999999999/currency")
    expect(status == 200, "GET /guides/<unknown id>/currency still returns 200")
    expect(
        "No currency information" in response.text,
        "an unknown destination id shows a not-found message, not an error",
    )

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Australia"})
    expect(status == 200, "GET /guides?query=Australia returns 200")
    expect("Sydney" in response.text, "searching by country returns its cities")
    expect("Tokyo" not in response.text, "searching by country excludes the other country")

    status, response = _call("GET", f"{API_BASE}/guides", params={"query": "Japan"})
    expect("Kyoto" in response.text, "searching for Japan returns Japanese cities")
    expect("Sydney" not in response.text, "searching for Japan excludes Australian cities")

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

    # Forgot / reset password, reusing the already-verified `email` account
    # since its password is not needed again after this point.
    run_forgot_password_checks(email)

    # AI Assistant, best effort on the model-grounded checks since ai-mode
    # is optional for this script, see the module docstring.
    run_ai_assistant_checks()

    run_mcp_rag_checks()

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