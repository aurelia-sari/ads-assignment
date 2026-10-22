"""Unit tests for sign-up and reset email delivery in student-4-api.

No network and no mail server. SMTP is the default and what CI and local runs
use. MAIL_PROVIDER=resend, as in the cloud, posts to the Resend API.

    python -m pytest student-4/tests/test_email_delivery.py
"""

import smtplib
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

import app as api  # noqa: E402

LINK_CODE = "tok123"


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send_message(self, message):
        FakeSMTP.sent.append(message)


class FakeResponse:
    def __init__(self, status=200, text=""):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(api, "MAIL_PROVIDER", "smtp")
    monkeypatch.setattr(
        requests, "post",
        lambda *a, **k: pytest.fail("the smtp provider must not call the Resend API"),
    )


@pytest.fixture
def resend(monkeypatch):
    posts = []

    def fake_post(url, **kwargs):
        posts.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(api, "MAIL_PROVIDER", "resend")
    monkeypatch.setattr(api, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(api, "MAIL_FROM", "NextStop <no-reply@example.com>")
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: pytest.fail("resend must not use SMTP"))
    return posts


def test_smtp_sends_through_mailpit(smtp):
    api.send_verification_email("Aurelia", "a@example.com", LINK_CODE)

    message = FakeSMTP.sent[0]
    assert message["To"] == "a@example.com"
    assert message["Subject"] == "Verify your NextStop account"
    assert f"/api/student-4/auth/verify/{LINK_CODE}" in message.get_payload()


def test_resend_verification_email_payload(resend):
    api.send_verification_email("Aurelia", "a@example.com", LINK_CODE)

    url, kwargs = resend[0]
    assert url == "https://api.resend.com/emails"
    assert kwargs["headers"] == {"Authorization": "Bearer re_test_key"}
    assert kwargs["timeout"] == api.RESEND_TIMEOUT_SECONDS
    body = kwargs["json"]
    assert body["from"] == "NextStop <no-reply@example.com>"
    assert body["to"] == ["a@example.com"]
    assert body["subject"] == "Verify your NextStop account"
    assert f"/api/student-4/auth/verify/{LINK_CODE}" in body["text"]
    assert "Hi Aurelia" in body["text"]


def test_resend_reset_email_payload(resend):
    api.send_reset_email("a@example.com", LINK_CODE)

    body = resend[0][1]["json"]
    assert body["to"] == ["a@example.com"]
    assert body["subject"] == "Reset your NextStop password"
    assert f"/student-4/reset-password.html?token={LINK_CODE}" in body["text"]


def test_resend_without_a_key_fails_without_a_call(monkeypatch, resend):
    monkeypatch.setattr(api, "RESEND_API_KEY", "")

    with pytest.raises(OSError, match="RESEND_API_KEY"):
        api.send_reset_email("a@example.com", LINK_CODE)
    assert resend == []


def test_resend_refusal_surfaces_as_an_oserror(monkeypatch, resend):
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: FakeResponse(403, "The example.com domain is not verified")
    )

    with pytest.raises(OSError):
        api.send_verification_email("Aurelia", "a@example.com", LINK_CODE)


def test_resend_timeout_surfaces_as_an_oserror(monkeypatch, resend):
    def slow(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(requests, "post", slow)

    with pytest.raises(OSError):
        api.send_reset_email("a@example.com", LINK_CODE)


class SharedReply:
    status_code = 200

    def json(self):
        return {}


def forgot_password(monkeypatch, resend_reply):
    """Posts to the route with the shared API recording the token, then Resend replying as given."""
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return resend_reply if url == api.RESEND_URL else SharedReply()

    monkeypatch.setattr(requests, "post", fake_post)
    api.app.config["TESTING"] = True
    response = api.app.test_client().post("/auth/forgot-password", json={"email": "student4@example.com"})
    return response, calls


def test_forgot_password_emails_the_link_through_resend(monkeypatch, resend):
    response, calls = forgot_password(monkeypatch, FakeResponse())

    assert response.status_code == 200
    token = calls[0][1]["json"]["reset_token"]
    sent = calls[1][1]["json"]
    assert sent["to"] == ["student4@example.com"]
    assert f"token={token}" in sent["text"]


def test_forgot_password_returns_503_when_resend_refuses(monkeypatch, resend):
    response, _ = forgot_password(monkeypatch, FakeResponse(403, "domain not verified"))

    assert response.status_code == 503
    assert b"Could not send the email" in response.data
    assert b"domain not verified" not in response.data
