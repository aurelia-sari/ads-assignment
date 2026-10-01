"""Unit tests for the Travel Guides AI assistant's fallback replies.

The database is stubbed, and none of these paths call the model.

    python -m pytest student-4/tests/test_orchestrator.py
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from agentic_loop.collectors import guide_collector  # noqa: E402
from agentic_loop.core import orchestrator  # noqa: E402
from agentic_loop.core.classifier import extract_destination  # noqa: E402

DESTINATIONS = [
    {"id": 1, "country": "Australia", "city": "Sydney", "region": "New South Wales"},
    {"id": 7, "country": "Australia", "city": "Cairns", "region": "Queensland"},
    {"id": 14, "country": "Japan", "city": "Tokyo", "region": "Tokyo"},
]


@pytest.fixture
def seeded(monkeypatch):
    monkeypatch.setattr(guide_collector, "collect_redirect_map", lambda: [])
    monkeypatch.setattr(guide_collector, "collect_destinations", lambda: DESTINATIONS)


def run(question):
    return orchestrator.run(question, lambda: extract_destination(question, DESTINATIONS))


def test_unknown_city_lists_the_cities_with_guides(seeded):
    result = run("How's the weather in Alice Springs?")
    assert result["intent"] == "weather"
    assert result["adapted"] is True
    assert result["answer"] == (
        "I only have guides for Australia (Cairns and Sydney) and Japan (Tokyo). "
        "Which of these cities would you like to know about?"
    )


def test_bare_unknown_place_lists_the_cities_with_guides(seeded):
    result = run("Alice Springs")
    assert result["intent"] == "unrelated"
    assert "Australia (Cairns and Sydney) and Japan (Tokyo)" in result["answer"]


def test_bare_known_city_asks_which_topic(seeded):
    result = run("Tokyo")
    assert result["intent"] == "unrelated"
    assert result["adapted"] is True
    assert result["answer"].startswith("What would you like to know about Tokyo, Japan?")


def test_unrelated_question_in_a_session_does_not_assume_the_city(seeded):
    # The resolver falls back to the session's city, but the question never named it.
    result = orchestrator.run("What is the capital of France?", lambda: DESTINATIONS[0])
    assert "I can only help with" in result["answer"]


def test_messages_still_work_without_the_database(monkeypatch):
    monkeypatch.setattr(guide_collector, "collect_redirect_map", lambda: [])
    monkeypatch.setattr(guide_collector, "collect_destinations", lambda: [])

    assert run("How's the weather in Alice Springs?")["answer"] == "Which city would you like to know about?"
    assert run("Alice Springs")["answer"] == (
        "I can only help with the currency, transportation, visa, weather and safety guide. "
        "Ask me about one of those, naming a city."
    )
