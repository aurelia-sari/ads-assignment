"""Unit tests for the stricter checks on AI Assistant currency answers.

The model is replaced by scripted answers, and student-4-db and the rates
are stubbed, so these need no network.

    python -m pytest student-4/tests/test_currency_validation.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from agentic_loop.collectors import guide_collector  # noqa: E402
from agentic_loop.core import orchestrator  # noqa: E402
from agentic_loop.core.classifier import classify_intent, extract_destination  # noqa: E402
from agentic_loop.core.validator import validate_answer  # noqa: E402
from agentic_loop.pipelines import guide_chat_pipeline  # noqa: E402
from services import exchange_rates  # noqa: E402

DESTINATIONS = [
    {"id": 1, "country": "Australia", "city": "Sydney", "region": "New South Wales"},
    {"id": 17, "country": "Japan", "city": "Kyoto", "region": "Kyoto Prefecture"},
    {"id": 18, "country": "Japan", "city": "Nara", "region": "Nara Prefecture"},
]
# The seeded tips from student-4/db/init_db.py.
CURRENCY = {
    1: {"currency_code": "AUD", "currency_name": "Australian Dollar", "exchange_tips": (
        "Cards are accepted almost everywhere. Carry a little cash for small regional towns and "
        "markets. One AUD equals 100 cents.")},
    17: {"currency_code": "JPY", "currency_name": "Japanese Yen", "exchange_tips": (
        "Cash is still common, especially at small restaurants, shrines and local shops. Most "
        "convenience store ATMs accept foreign cards. The yen has no smaller unit in everyday use.")},
}
RATES = {
    "AUD": {"USD": 0.69675, "EUR": 0.61361, "GBP": 0.52441, "JPY": 109.39},
    "JPY": {"USD": 0.00637, "EUR": 0.00561, "GBP": 0.00479, "AUD": 0.00914},
}


@pytest.fixture(autouse=True)
def stubbed(monkeypatch):
    monkeypatch.setattr(guide_collector, "collect_redirect_map", lambda: [])
    monkeypatch.setattr(guide_collector, "collect_destinations", lambda: DESTINATIONS)
    monkeypatch.setattr(guide_collector, "collect_currency", lambda destination_id: CURRENCY[destination_id])
    monkeypatch.setattr(exchange_rates, "LIVE_DATA_ENABLED", True)
    monkeypatch.setattr(exchange_rates, "latest", lambda base: {
        "base": base, "date": "2026-09-30", "rates": RATES[base],
        "fetched_at": datetime(2026, 10, 1, 5, 3, tzinfo=timezone.utc),
    })


@pytest.fixture
def model(monkeypatch):
    """Scripted model answers, one per call, and the questions it was asked."""

    class Model(list):
        asked = []

    answers = Model()

    def fake_ask(question, system, context):
        answers.asked.append(question)
        return answers.pop(0)

    monkeypatch.setattr(guide_chat_pipeline, "ask_ai", fake_ask)
    return answers


def ask(question):
    return orchestrator.run(question, lambda: extract_destination(question, DESTINATIONS))


def checks_for(destination_id):
    context, fact_tokens, _ = guide_chat_pipeline.gather_guide_facts("currency", destination_id)
    return fact_tokens, guide_chat_pipeline.currency_checks(context)


# Answers that contradict the guide

# Each shares a word with the guide, so the original check alone passed it.

@pytest.mark.parametrize("answer", [
    "You do not need cash in Sydney, as cards are accepted almost everywhere.",
    "You don't really need cash in Sydney, cards are accepted at markets too.",
    "Sydney is basically cashless, so there is no need to carry cash in regional towns.",
])
def test_sydney_answer_saying_no_cash_is_needed_is_rejected(answer):
    fact_tokens, checks = checks_for(1)
    assert validate_answer(answer, fact_tokens)["valid"]
    assert validate_answer(answer, fact_tokens, **checks) == {"valid": False, "reason": "contradicts_guide"}


@pytest.mark.parametrize("answer", [
    "Cards work almost everywhere in Kyoto, even at convenience stores.",
    "In Kyoto cards are accepted almost everywhere, including shrines.",
    "You can pay by card everywhere in Kyoto, even at small restaurants.",
])
def test_kyoto_answer_saying_cards_work_everywhere_is_rejected(answer):
    fact_tokens, checks = checks_for(17)
    assert validate_answer(answer, fact_tokens)["valid"]
    assert validate_answer(answer, fact_tokens, **checks) == {"valid": False, "reason": "contradicts_guide"}


@pytest.mark.parametrize("destination_id, answer", [
    (1, "Cards are accepted almost everywhere in Sydney, but carry a little cash for small regional towns."),
    (17, "Cash is still common in Kyoto, especially at small restaurants and shrines."),
    (17, "Most convenience store ATMs accept foreign cards, so you can withdraw yen easily."),
])
def test_answers_that_follow_the_guide_still_pass(destination_id, answer):
    fact_tokens, checks = checks_for(destination_id)
    assert validate_answer(answer, fact_tokens, **checks)["valid"]


# Figures

def test_a_rate_from_the_context_passes():
    fact_tokens, checks = checks_for(1)
    assert validate_answer("Right now 1 USD = 1.44 AUD.", fact_tokens, **checks)["valid"]


@pytest.mark.parametrize("answer", [
    "Right now 1 USD is about 1.52 AUD.",
    "100 JPY is roughly 0.95 AUD today.",
])
def test_an_invented_rate_is_rejected(answer):
    fact_tokens, checks = checks_for(1)
    assert validate_answer(answer, fact_tokens, **checks) == {"valid": False, "reason": "unknown_figure"}


def test_figures_are_compared_without_commas_or_trailing_zeros():
    fact_tokens, checks = checks_for(17)
    assert validate_answer("1 USD is 157.00 JPY, and 1 GBP is 209 JPY.", fact_tokens, **checks)["valid"]


def test_other_topics_keep_the_original_check():
    assert validate_answer("Expect about 31C and heavy rain.", ["31"])["valid"]
    assert not validate_answer("Expect warm weather.", ["31"])["valid"]


# The whole loop

def test_a_contradicting_answer_is_retried(model):
    model.extend([
        "You do not need cash in Sydney, as cards are accepted almost everywhere.",
        "Cards are accepted almost everywhere, but carry a little cash for small regional towns and markets.",
    ])
    result = ask("Do I need cash in Sydney?")
    assert result == {
        "intent": "currency",
        "answer": "Cards are accepted almost everywhere, but carry a little cash for small regional towns and markets.",
        "adapted": False,
    }
    assert "exact facts" in model.asked[1]


def test_two_contradicting_answers_fall_back_to_the_guide_text(model):
    model.extend([
        "Cards work almost everywhere in Kyoto, even at convenience stores.",
        "You can pay by card everywhere in Kyoto, even at small restaurants.",
    ])
    result = ask("Do I need cash in Kyoto?")
    assert result["adapted"] is True
    assert result["answer"] == "Here is what the guide says for Kyoto, Japan. " + CURRENCY[17]["exchange_tips"]
    assert result["redirect_path"] == "/student-4/#guides"


def test_a_correct_first_answer_is_returned_unchanged(model):
    model.append("Cash is still common in Kyoto, especially at small restaurants, shrines and local shops.")
    result = ask("Do I need cash in Kyoto?")
    assert result["adapted"] is False
    assert len(model.asked) == 1


def test_other_topics_keep_the_rephrase_fallback(model, monkeypatch):
    monkeypatch.setattr(guide_collector, "collect_safety", lambda destination_id: {
        "safety_level": "Exercise normal safety precautions", "tips": "Watch for surf rips at beaches."})
    model.extend(["It is fine.", "It is fine."])
    result = ask("Is Sydney safe?")
    assert result["answer"].startswith("I want to get this right for Sydney, Australia.")


# Card and ATM questions reach the currency guide

@pytest.mark.parametrize("question, intent", [
    ("Can I pay by card everywhere in Osaka?", "currency"),
    ("Are there ATMs in Nara?", "currency"),
    ("Will my credit card work in Kyoto?", "currency"),
    ("What is the atmosphere like in Kyoto?", "unrelated"),
    ("Is Kyoto safe at night?", "safety"),
])
def test_card_and_atm_questions_are_currency_questions(question, intent):
    assert classify_intent(question, [])[0] == intent
