"""Unit tests for the student-4 Multi-Agent endpoints.

No network and no running services. The Multi-Agent Server and student-4-db
are replaced with stubs, so these run in CI where MULTI_AGENT_ENABLED is false.

    python -m pytest student-4/tests/test_multi_agent.py
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from agentic_loop.collectors import guide_collector  # noqa: E402
from app import app  # noqa: E402
from routes import multi_agent  # noqa: E402
from services import multi_agent_client  # noqa: E402

WORKFLOW_ID = "wf-20260101-000000-abc123"
KYOTO = {"id": 7, "city": "Kyoto", "country": "Japan"}


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


def workflow(status="awaiting_human_review", **extra):
    return {
        "id": WORKFLOW_ID,
        "status": status,
        "round": 1,
        "task": "Write a short pre-trip briefing for Kyoto",
        "plan": {"steps": ["Read the guide"]},
        "evidence": [{"id": "E1", "kind": "supplied", "ok": True}],
        "attempts": [{
            "worker": {"response": "Carry some cash [E1]. <script>alert(1)</script>"},
            "review": {"verdict": "pass", "risks": [], "recommendations": []},
        }],
        "decisions": [],
        **extra,
    }


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a disabled integration must not make a network call")

    monkeypatch.setattr(requests, "request", refuse)
    monkeypatch.setattr(requests, "get", refuse)
    monkeypatch.setattr(requests, "post", refuse)


@pytest.fixture
def disabled(monkeypatch, no_network):
    monkeypatch.setattr(multi_agent_client, "MULTI_AGENT_ENABLED", False)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(multi_agent_client, "MULTI_AGENT_ENABLED", True)
    monkeypatch.setattr(multi_agent, "collect_destinations", lambda: [KYOTO])
    # no_city_message reads the covered cities through the collector module.
    monkeypatch.setattr(guide_collector, "collect_destinations", lambda: [KYOTO])
    monkeypatch.setattr(
        multi_agent, "gather_guide_facts",
        lambda topic, destination_id: (f"{topic} facts", [], topic != "visa"),
    )


def stub_server(monkeypatch, response):
    sent = []

    def fake_request(method, url, **kwargs):
        sent.append((method, url, kwargs))
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(requests, "request", fake_request)
    return sent


def test_start_is_disabled_without_a_network_call(client, disabled):
    response = client.post("/ai/multi-agent", data={"city": "Kyoto"})
    assert response.status_code == 200
    assert b"MULTI_AGENT_ENABLED=false" in response.data


@pytest.mark.parametrize("path", [
    "/ai/multi-agent",
    f"/ai/multi-agent/{WORKFLOW_ID}",
    f"/ai/multi-agent/{WORKFLOW_ID}/history",
])
def test_reads_are_disabled_without_a_network_call(client, disabled, path):
    response = client.get(path)
    assert response.status_code == 200
    assert b"MULTI_AGENT_ENABLED=false" in response.data


def test_decision_is_disabled_without_a_network_call(client, disabled):
    response = client.post(
        f"/ai/multi-agent/{WORKFLOW_ID}/decision", data={"decision": "approve", "reviewer": "Aurelia"}
    )
    assert response.status_code == 200
    assert b"MULTI_AGENT_ENABLED=false" in response.data


def test_start_requires_a_city(client, enabled):
    assert client.post("/ai/multi-agent", data={"city": " "}).status_code == 400


def test_start_unknown_city_lists_the_covered_cities(client, enabled, monkeypatch):
    sent = stub_server(monkeypatch, FakeResponse(workflow(), 201))
    response = client.post("/ai/multi-agent", data={"city": "Atlantis"})
    assert response.status_code == 404
    assert b"I only have guides for" in response.data
    assert sent == []


def test_start_sends_guide_evidence_and_mcp_call(client, enabled, monkeypatch):
    sent = stub_server(monkeypatch, FakeResponse(workflow(), 201))
    response = client.post("/ai/multi-agent", data={"city": "Kyoto", "reviewer": "Aurelia"})

    assert response.status_code == 200
    method, url, kwargs = sent[0]
    body = kwargs["json"]
    assert (method, url.endswith("/workflows")) == ("POST", True)
    assert body["feature"] == "student-4"
    assert body["mcp_calls"] == [{"tool": "lookup_destination_guide", "arguments": {"query": "Kyoto"}}]
    # Visa has no data in the stub, so it is left out rather than sent empty.
    assert [e["label"] for e in body["evidence"]] == [
        f"Travel guide {t} for Kyoto, Japan" for t in ("currency", "transport", "weather", "safety")
    ]
    assert body["requested_by"] == "student-4-ui:Aurelia"
    assert b"awaiting_human_review" in response.data
    assert b"Human review" in response.data


def test_model_output_is_escaped(client, enabled, monkeypatch):
    stub_server(monkeypatch, FakeResponse(workflow(), 201))
    response = client.post("/ai/multi-agent", data={"city": "Kyoto"})
    assert b"<script>" not in response.data
    assert b"&lt;script&gt;" in response.data


def test_in_flight_workflow_polls_itself(client, enabled, monkeypatch):
    stub_server(monkeypatch, FakeResponse(workflow("working", attempts=[]), 202))
    response = client.post("/ai/multi-agent", data={"city": "Kyoto"})
    assert b"hx-trigger='load delay:5s'" in response.data
    assert b"Human review" not in response.data


def test_server_down_returns_503_notice(client, enabled, monkeypatch):
    stub_server(monkeypatch, requests.ConnectionError("refused"))
    response = client.post("/ai/multi-agent", data={"city": "Kyoto"})
    assert response.status_code == 503
    assert b"Could not reach the shared Multi-Agent Server" in response.data


def test_server_refusal_keeps_its_status(client, enabled, monkeypatch):
    stub_server(monkeypatch, FakeResponse({"error": "task is required"}, 400))
    response = client.post("/ai/multi-agent", data={"city": "Kyoto"})
    assert response.status_code == 400
    assert b"task is required" in response.data


def test_bad_workflow_id_is_refused_before_any_call(client, enabled, no_network):
    for path in ("/ai/multi-agent/not-an-id", "/ai/multi-agent/not-an-id/history"):
        assert client.get(path).status_code == 400
    assert client.post("/ai/multi-agent/not-an-id/decision", data={"reviewer": "A"}).status_code == 400


def test_decision_requires_a_reviewer_name(client, enabled, no_network):
    response = client.post(f"/ai/multi-agent/{WORKFLOW_ID}/decision", data={"decision": "approve"})
    assert response.status_code == 400


def test_correct_sends_comment_as_feedback(client, enabled, monkeypatch):
    sent = stub_server(monkeypatch, FakeResponse(workflow("working", round=2), 200))
    client.post(
        f"/ai/multi-agent/{WORKFLOW_ID}/decision",
        data={"decision": "correct", "reviewer": "Aurelia", "comment": "Mention cash"},
    )
    body = sent[0][2]["json"]
    assert (body["feedback"], body["notes"]) == ("Mention cash", "")


def test_reject_sends_comment_as_notes(client, enabled, monkeypatch):
    sent = stub_server(monkeypatch, FakeResponse(workflow("rejected", decisions=[
        {"decision": "reject", "reviewer": "Aurelia", "notes": "Too vague"},
    ]), 200))
    response = client.post(
        f"/ai/multi-agent/{WORKFLOW_ID}/decision",
        data={"decision": "reject", "reviewer": "Aurelia", "comment": "Too vague"},
    )
    body = sent[0][2]["json"]
    assert (body["notes"], body["feedback"]) == ("Too vague", "")
    assert b"Decision: reject by Aurelia" in response.data


def test_stale_decision_shows_the_current_workflow(client, enabled, monkeypatch):
    calls = iter([
        FakeResponse({"error": "workflow is approved, not awaiting_human_review"}, 409),
        FakeResponse(workflow("approved", final_response="Done"), 200),
    ])
    monkeypatch.setattr(requests, "request", lambda *a, **k: next(calls))
    response = client.post(
        f"/ai/multi-agent/{WORKFLOW_ID}/decision", data={"decision": "approve", "reviewer": "Aurelia"}
    )
    assert response.status_code == 409
    assert b"Released response" in response.data
