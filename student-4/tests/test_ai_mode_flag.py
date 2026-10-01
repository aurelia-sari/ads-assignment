"""Unit tests for AI_MODE_ENABLED=false, as in CI.

AI-Mode, student-4-db, shared-api and the live APIs are stubbed, with a
guard that fails on any call to AI-Mode, so these need no network.

    python -m pytest student-4/tests/test_ai_mode_flag.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app import app  # noqa: E402
from agentic_loop.collectors import guide_collector  # noqa: E402
from agentic_loop.core import orchestrator  # noqa: E402
from agentic_loop.core.classifier import extract_destination  # noqa: E402
from routes import ai_chat  # noqa: E402
from services import ai_client, database_api, exchange_rates, weather  # noqa: E402

DESTINATIONS = [
    {"id": 1, "country": "Australia", "city": "Sydney", "region": "New South Wales"},
    {"id": 18, "country": "Japan", "city": "Nara", "region": "Nara Prefecture"},
]
CURRENCY = {
    1: {"currency_code": "AUD", "currency_name": "Australian Dollar",
        "exchange_tips": "Cards are accepted almost everywhere. Carry a little cash for small regional towns."},
    18: {"currency_code": "JPY", "currency_name": "Japanese Yen",
         "exchange_tips": "Cash is still common, especially at small restaurants, shrines and local shops."},
}
MONTHS = [
    {"month": "July", "avg_temp": 32, "rainfall": 174, "best_visit_time": "Spring and autumn are popular."},
    {"month": "August", "avg_temp": 33, "rainfall": 128, "best_visit_time": "Spring and autumn are popular."},
]


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def ai_mode_off(monkeypatch):
    monkeypatch.setattr(ai_client, "AI_MODE_ENABLED", False)

    def refuse(*args, **kwargs):
        raise AssertionError("AI_MODE_ENABLED=false must not call AI-Mode")

    monkeypatch.setattr(requests, "post", refuse)
    monkeypatch.setattr(weather, "LIVE_DATA_ENABLED", False)
    monkeypatch.setattr(guide_collector, "collect_redirect_map", lambda: [
        {"keyword": "hotel", "feature_name": "Bookings & Budget", "redirect_path_template": "/student-5/#search"}])
    monkeypatch.setattr(guide_collector, "collect_destinations", lambda: DESTINATIONS)
    monkeypatch.setattr(guide_collector, "collect_destination",
                        lambda destination_id: next(d for d in DESTINATIONS if d["id"] == destination_id))
    monkeypatch.setattr(guide_collector, "collect_currency", lambda destination_id: CURRENCY[destination_id])
    monkeypatch.setattr(guide_collector, "collect_weather", lambda destination_id: MONTHS)
    monkeypatch.setattr(guide_collector, "collect_safety", lambda destination_id: {
        "safety_level": "Exercise normal safety precautions", "tips": "Watch for surf rips at beaches."})
    monkeypatch.setattr(exchange_rates, "LIVE_DATA_ENABLED", True)
    monkeypatch.setattr(exchange_rates, "latest", lambda base: {
        "base": base, "date": "2026-09-30",
        "rates": {"USD": 0.69675, "EUR": 0.61361, "GBP": 0.52441, "JPY": 109.39},
        "fetched_at": datetime(2026, 10, 1, 5, 3, tzinfo=timezone.utc),
    })


def ask(question):
    return orchestrator.run(question, lambda: extract_destination(question, DESTINATIONS))


def test_the_client_makes_no_network_call():
    with pytest.raises(ai_client.AIModeDisabled):
        ai_client.ask_ai("hello", "system")


def test_a_named_month_gets_the_guide_figures():
    result = ask("What is the weather like in Nara in August?")
    assert result["adapted"] is True
    assert result["answer"] == (
        "Here is what the guide says for Nara, Japan. The average daytime high in August "
        "is about 33°C, with around 128mm of rainfall."
    )


def test_a_currency_question_gets_the_guide_tip():
    result = ask("Do I need cash in Nara?")
    assert result["answer"] == "Here is what the guide says for Nara, Japan. " + CURRENCY[18]["exchange_tips"]


def test_other_questions_link_the_guide_page():
    result = ask("Is Sydney safe?")
    assert result["intent"] == "safety"
    assert result["answer"].startswith("The AI model is switched off here")
    assert result["redirect_path"] == "/student-4/#guides"


@pytest.mark.parametrize("question, start", [
    ("How much is 500 AUD to yen?", "500 AUD is about 54,695 JPY"),
    ("Can you find me a hotel in Sydney?", "That sounds like a job for Bookings & Budget"),
    ("What's the weather like?", "I only have guides for"),
])
def test_answers_that_need_no_model_still_work(question, start):
    assert ask(question)["answer"].startswith(start)


def test_the_chat_route_returns_200_not_503(monkeypatch):
    monkeypatch.setattr(ai_chat, "is_authenticated", lambda user_id: True)
    monkeypatch.setattr(ai_chat, "collect_destinations", guide_collector.collect_destinations)
    monkeypatch.setattr(ai_chat, "collect_destination", guide_collector.collect_destination)
    monkeypatch.setattr(database_api, "create_chat_session",
                        lambda user_id, destination_id: FakeResponse({"id": 7}, 201))
    monkeypatch.setattr(database_api, "add_chat_message", lambda *args, **kwargs: FakeResponse({}, 201))
    app.config["TESTING"] = True

    response = app.test_client().post(
        "/ai/guide-chat", json={"user_id": 4, "question": "What is the weather like in Nara in July?"}
    )
    assert response.status_code == 200
    assert "about 32°C, with around 174mm" in response.get_json()["answer"]
