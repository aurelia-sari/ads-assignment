"""Unit tests for the live exchange rates in the Travel Guides currency section.

Frankfurter and student-4-db are stubbed, so these need no network and run
in CI where GUIDES_LIVE_DATA is false.

    python -m pytest student-4/tests/test_exchange_rates.py
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app import app  # noqa: E402
from agentic_loop.collectors import guide_collector  # noqa: E402
from agentic_loop.pipelines.guide_chat_pipeline import gather_guide_facts  # noqa: E402
from services import exchange_rates  # noqa: E402

HTMX = {"HX-Request": "true"}

AUD_RATES = {"amount": 1.0, "base": "AUD", "date": "2026-09-30",
             "rates": {"USD": 0.69675, "EUR": 0.61361, "GBP": 0.52441, "JPY": 109.39}}
JPY_RATES = {"amount": 1.0, "base": "JPY", "date": "2026-09-30",
             "rates": {"USD": 0.00637, "EUR": 0.00561, "GBP": 0.00479, "AUD": 0.00914}}
CURRENCY_ROWS = {
    1: {"currency_code": "AUD", "currency_name": "Australian Dollar", "exchange_tips": "Cards are accepted."},
    14: {"currency_code": "JPY", "currency_name": "Japanese Yen", "exchange_tips": "Cash is still common."},
}


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    exchange_rates._cache.clear()
    monkeypatch.setattr(exchange_rates, "LIVE_DATA_ENABLED", True)


@pytest.fixture
def frankfurter_calls(monkeypatch):
    """Stubs both student-4-db and Frankfurter. Set calls.reply to change
    what Frankfurter returns. Every Frankfurter call is recorded."""

    class Calls(list):
        reply = None

    calls = Calls()

    def fake_get(url, params=None, **kwargs):
        if "frankfurter" in url:
            calls.append(params)
            if isinstance(calls.reply, Exception):
                raise calls.reply
            if calls.reply is not None:
                return calls.reply
            return FakeResponse(AUD_RATES if params["base"] == "AUD" else JPY_RATES)
        destination_id = int(url.rstrip("/").split("/")[-2])
        row = CURRENCY_ROWS.get(destination_id)
        return FakeResponse(row) if row else FakeResponse({"error": "not found"}, 404)

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


# Live

def test_australian_city_shows_foreign_currency_in_aud(client, frankfurter_calls):
    html = client.get("/guides/1/currency/live", headers=HTMX).get_data(as_text=True)
    assert "1 USD = 1.44 AUD" in html
    assert "1 EUR = 1.63 AUD" in html
    assert "1 GBP = 1.91 AUD" in html
    assert "100 JPY = 0.91 AUD" in html
    assert "published 30 September 2026" in html
    assert frankfurter_calls[0] == {"base": "AUD", "symbols": "USD,EUR,GBP,JPY"}


def test_converter_starts_at_100_of_the_first_currency(client, frankfurter_calls):
    html = client.get("/guides/1/currency/live", headers=HTMX).get_data(as_text=True)
    assert "data-fx-base='AUD'" in html
    assert "&quot;USD&quot;: 0.69675" in html
    assert "data-fx-side='foreign' value='100'" in html
    assert "data-fx-side='local' value='143.52'" in html
    assert "<option value='JPY'>JPY</option>" in html


def test_japanese_city_shows_foreign_currency_in_jpy(client, frankfurter_calls):
    body = client.get("/guides/14/currency/live").get_json()
    assert body["status"] == "ok"
    assert body["lines"] == ["1 USD = 157 JPY", "1 EUR = 178 JPY", "1 GBP = 209 JPY", "1 AUD = 109 JPY"]


def test_detail_page_loads_the_live_rates_after_rendering(client, monkeypatch):
    def fake_get(url, **kwargs):
        if url.endswith("/destinations/1"):
            return FakeResponse({"id": 1, "country": "Australia", "city": "Sydney", "region": "NSW"})
        if url.endswith("/currency"):
            return FakeResponse(CURRENCY_ROWS[1])
        if "frankfurter" in url:
            raise AssertionError("the guide page must not wait for the rates API")
        return FakeResponse([] if not url.endswith("/safety") else None, 404)

    monkeypatch.setattr(requests, "get", fake_get)
    html = client.get("/guides/1").get_data(as_text=True)
    assert "hx-get='/api/student-4/guides/1/currency/live'" in html
    assert "hx-trigger='load'" in html


# Disabled, as in CI

def test_disabled_makes_no_network_call(client, monkeypatch):
    monkeypatch.setattr(exchange_rates, "LIVE_DATA_ENABLED", False)

    def refuse(*args, **kwargs):
        raise AssertionError("disabled live data must not make a network call")

    monkeypatch.setattr(requests, "get", refuse)

    response = client.get("/guides/1/currency/live")
    assert response.status_code == 200
    assert response.get_json()["status"] == "disabled"

    html = client.get("/guides/1/currency/live", headers=HTMX).get_data(as_text=True)
    assert "switched off" in html


# Timeout and bad responses

def test_timeout_falls_back_to_a_clear_note(client, frankfurter_calls):
    frankfurter_calls.reply = requests.Timeout("read timed out")

    response = client.get("/guides/1/currency/live")
    assert response.status_code == 503
    assert response.get_json()["status"] == "unavailable"

    response = client.get("/guides/1/currency/live", headers=HTMX)
    assert response.status_code == 200
    assert "could not be loaded right now" in response.get_data(as_text=True)


@pytest.mark.parametrize("reply", [
    FakeResponse({"message": "not found"}, 404),
    FakeResponse(ValueError("not JSON")),
    FakeResponse({"base": "AUD", "date": "2026-09-30", "rates": {"USD": 0.69}}),
    FakeResponse({"base": "AUD", "date": "2026-09-30",
                  "rates": {"USD": 0, "EUR": 0.6, "GBP": 0.5, "JPY": 109}}),
], ids=["http-error", "not-json", "missing-rate", "zero-rate"])
def test_bad_response_falls_back_to_a_clear_note(client, frankfurter_calls, reply):
    frankfurter_calls.reply = reply
    response = client.get("/guides/1/currency/live")
    assert response.status_code == 503
    assert response.get_json()["status"] == "unavailable"


def test_unknown_destination_returns_not_found(client, frankfurter_calls):
    assert client.get("/guides/999/currency/live").status_code == 404
    assert frankfurter_calls == []


# Cache

def test_rates_are_cached(client, frankfurter_calls):
    client.get("/guides/1/currency/live")
    client.get("/guides/1/currency/live")
    assert len(frankfurter_calls) == 1


def test_expired_rates_are_refreshed(client, frankfurter_calls, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(exchange_rates.time, "monotonic", lambda: clock[0])
    client.get("/guides/1/currency/live")
    clock[0] += exchange_rates.CACHE_TTL_SECONDS + 1
    client.get("/guides/1/currency/live")
    assert len(frankfurter_calls) == 2


def test_last_good_rates_are_kept_when_a_refresh_fails(client, frankfurter_calls, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(exchange_rates.time, "monotonic", lambda: clock[0])
    client.get("/guides/1/currency/live")

    clock[0] += exchange_rates.CACHE_TTL_SECONDS + 1
    frankfurter_calls.reply = requests.ConnectionError("refused")
    body = client.get("/guides/1/currency/live").get_json()
    assert body["status"] == "ok"
    assert "1 USD = 1.44 AUD" in body["lines"]


def test_a_failed_call_is_not_retried_straight_away(client, frankfurter_calls):
    frankfurter_calls.reply = requests.Timeout("read timed out")
    client.get("/guides/1/currency/live")
    client.get("/guides/1/currency/live")
    assert len(frankfurter_calls) == 1


# AI Assistant grounding

@pytest.fixture
def sydney_currency(monkeypatch):
    monkeypatch.setattr(guide_collector, "collect_currency", lambda destination_id: CURRENCY_ROWS[1])


def test_ai_uses_the_same_rates_as_the_page(frankfurter_calls, sydney_currency):
    context, fact_tokens, has_data = gather_guide_facts("currency", 1)
    assert has_data
    assert "- 1 USD = 1.44 AUD" in context
    assert "1.44" in fact_tokens
    assert "0.91" in fact_tokens


def test_ai_is_told_not_to_quote_a_rate_when_none_is_available(monkeypatch, sydney_currency):
    monkeypatch.setattr(exchange_rates, "LIVE_DATA_ENABLED", False)
    context, fact_tokens, has_data = gather_guide_facts("currency", 1)
    assert has_data
    assert "do not quote any rate" in context
    assert "AUD" in fact_tokens
