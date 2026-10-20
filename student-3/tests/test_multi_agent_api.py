"""Release 2 endpoint tests for the student-3 backend/API (Multi-Agent + browse).

    python -m pytest student-3/tests/test_multi_agent_api.py
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

import app as api  # noqa: E402
from services import multi_agent_client  # noqa: E402


@pytest.fixture
def client():
    api.app.config["TESTING"] = True
    return api.app.test_client()


def _db_response(posts):
    fake = Mock(status_code=200)
    fake.json.return_value = posts
    fake.raise_for_status = lambda: None
    return fake


def test_browse_trips_returns_trip_cards(client, monkeypatch):
    posts = [{
        "post_id": 1, "traveller_id": 2, "destination": "Bali, Indonesia",
        "start_date": "2026-10-12", "end_date": "2026-10-19",
        "travel_style": "into hiking", "note": "Volcano hikes", "status": "open",
    }]
    monkeypatch.setattr(api.requests, "get", lambda *a, **k: _db_response(posts))

    response = client.get("/trips?destination=Bali")

    assert response.status_code == 200
    assert b"Bali, Indonesia" in response.data
    assert b"into hiking" in response.data


def test_multi_agent_start_reports_switched_off(client, monkeypatch):
    monkeypatch.setattr(multi_agent_client, "MULTI_AGENT_ENABLED", False)
    monkeypatch.setattr(api, "_own_posts_evidence", lambda: [])

    response = client.post("/ai/multi-agent", data={"task": "Best match?", "reviewer": "ci"})

    assert response.status_code == 200
    assert b"switched off" in response.data


def test_multi_agent_rejects_a_malformed_workflow_id(client):
    response = client.get("/ai/multi-agent/not-a-workflow")

    assert response.status_code == 400
    assert b"not a workflow id" in response.data


def test_multi_agent_decision_requires_a_reviewer_name(client):
    response = client.post("/ai/multi-agent/wf-test-1/decision", data={"decision": "approve"})

    assert response.status_code == 400
    assert b"Enter your name" in response.data
