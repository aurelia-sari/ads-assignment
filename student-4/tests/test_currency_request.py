"""Unit tests for currency conversions in the Travel Guides AI Assistant.

Rates and student-4-db are stubbed, and conversions never call the model,
so these need no network.

    python -m pytest student-4/tests/test_currency_request.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from agentic_loop.collectors import guide_collector  # noqa: E402
from agentic_loop.core import currency_request, orchestrator  # noqa: E402
from agentic_loop.core.classifier import extract_destination  # noqa: E402
from services import exchange_rates  # noqa: E402

DESTINATIONS = [
    {"id": 1, "country": "Australia", "city": "Sydney", "region": "New South Wales"},
    {"id": 14, "country": "Japan", "city": "Tokyo", "region": "Tokyo Metropolis"},
]
CURRENCY_BY_ID = {1: "AUD", 14: "JPY"}
RATES = {
    "AUD": {"USD": 0.69675, "EUR": 0.61361, "GBP": 0.52441, "JPY": 109.39},
    "JPY": {"USD": 0.00637, "EUR": 0.00561, "GBP": 0.00479, "AUD": 0.00914},
}


@pytest.fixture(autouse=True)
def stubbed(monkeypatch):
    monkeypatch.setattr(guide_collector, "collect_redirect_map", lambda: [])
    monkeypatch.setattr(guide_collector, "collect_destinations", lambda: DESTINATIONS)
    monkeypatch.setattr(
        guide_collector, "collect_currency", lambda destination_id: {"currency_code": CURRENCY_BY_ID[destination_id]}
    )
    monkeypatch.setattr(exchange_rates, "LIVE_DATA_ENABLED", True)
    monkeypatch.setattr(exchange_rates, "latest", lambda base: {
        "base": base, "date": "2026-09-30", "rates": RATES[base],
        "fetched_at": datetime(2026, 10, 1, 5, 3, tzinfo=timezone.utc),
    })

    def no_model(*args, **kwargs):
        raise AssertionError("a conversion must not call the model")

    monkeypatch.setattr(orchestrator, "run_guide_chat", no_model)


def ask(question):
    return orchestrator.run(question, lambda: extract_destination(question, DESTINATIONS))


# Parsing

@pytest.mark.parametrize("question, amount, currencies", [
    ("How much is 500 AUD to yen?", 500, ["AUD", "JPY"]),
    ("Convert 1,250.50 US dollars into euros", 1250.5, ["USD", "EUR"]),
    ("What is £20 in Australian dollars?", 20, ["GBP", "AUD"]),
    ("How much is a euro worth in Sydney?", None, ["EUR"]),
])
def test_amount_and_currencies_are_read_in_order(question, amount, currencies):
    request = currency_request.parse(question)
    assert request["kind"] == "convert"
    assert request["amount"] == amount
    assert request["currencies"] == currencies


def test_a_question_without_a_currency_is_not_a_conversion():
    assert currency_request.parse("Do I need cash in Kyoto?") is None


def test_a_named_dollar_is_not_read_as_a_bare_dollar():
    assert currency_request.parse("Convert 100 New Zealand dollars to yen") == {"kind": "unsupported", "names": ["NZD"]}


# Conversions

def test_converts_between_two_named_currencies():
    result = ask("How much is 500 AUD to yen?")
    assert result["intent"] == "currency"
    assert result["adapted"] is False
    assert result["answer"].startswith("500 AUD is about 54,695 JPY, at 1 AUD = 109 JPY.")
    assert "published 30 September 2026" in result["answer"]


def test_converts_into_the_named_citys_currency():
    result = ask("How much is 200 USD in Tokyo?")
    assert result["answer"].startswith("200 USD is about 31,397 JPY")


def test_yen_rate_is_quoted_per_100_like_the_page():
    assert ask("Convert 1,000 yen to US dollars")["answer"].startswith(
        "1,000 JPY is about 6.37 USD, at 100 JPY = 0.64 USD."
    )


def test_converts_between_two_currencies_neither_city_uses():
    result = ask("Convert 100 euros to pounds")
    assert result["answer"].startswith("100 EUR is about 85.46 GBP, at 1 EUR = 0.85 GBP.")


def test_rate_question_without_an_amount_uses_one_unit():
    assert ask("How much is a euro worth in Sydney?")["answer"].startswith("1 EUR is about 1.63 AUD")


# Fallbacks

def test_unsupported_currency_lists_the_available_ones():
    result = ask("How much is 1000 baht in yen?")
    assert result["adapted"] is True
    assert result["answer"] == (
        "Only AUD, JPY, USD, EUR and GBP are available at the moment, so I cannot convert THB."
    )


def test_bare_dollars_asks_which_dollar():
    assert ask("How much is 500 dollars in yen?")["answer"].startswith("Which dollar do you mean?")


def test_one_currency_and_no_city_asks_what_to_convert_to():
    assert ask("Convert 300 GBP").get("answer") == (
        "Which currency should I convert GBP to? I can use AUD, JPY, USD and EUR."
    )


def test_the_citys_own_currency_gets_the_normal_guide_answer(monkeypatch):
    monkeypatch.setattr(orchestrator, "run_guide_chat", lambda question, intent, destination: {
        "answer": "Cash is still common in Japan.", "has_data": True, "fact_tokens": ["Cash"],
    })
    assert ask("Is 50000 yen enough for a week in Tokyo?")["answer"] == "Cash is still common in Japan."


def test_no_live_rates_says_so(monkeypatch):
    def disabled(base):
        raise exchange_rates.LiveDataDisabled("off")

    monkeypatch.setattr(exchange_rates, "latest", disabled)
    result = ask("How much is 500 AUD to yen?")
    assert "Live exchange rates are not available right now" in result["answer"]
    assert result["redirect_path"] == "/student-4/#guides"
