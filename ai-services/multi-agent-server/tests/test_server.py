"""Tests for the shared Multi-Agent Server.

AI-Mode and the MCP/RAG fetches are replaced with fakes, so these run without
Ollama or any other local service. The fakes return what a small local model
really returns often enough to matter: JSON wrapped in prose, and sometimes no
JSON at all.

    ai-services/.venv/bin/python -m pytest ai-services/multi-agent-server/tests -q
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GOOD_PLAN = json.dumps({
    "goal": "Summarise the trip",
    "steps": ["Read the trip", "Summarise it"],
    "required_evidence": ["S1"],
    "acceptance_criteria": ["Names the destination", "Cites the evidence"],
})
GOOD_REVIEW = json.dumps({
    "verdict": "pass",
    "criteria": [{"criterion": "Names the destination", "met": True, "note": "Tokyo"}],
    "risks": [],
    "recommendations": [],
})


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_DATA_DIR", str(tmp_path))
    for module in ("server", "agents", "evidence", "store"):
        sys.modules.pop(module, None)
    import agents
    import server

    replies = {"planner": [GOOD_PLAN], "worker": ["Your trip is to Tokyo [E1]."],
               "reviewer": [GOOD_REVIEW]}
    calls = []

    def fake_ai_mode(system, content, max_tokens=500):
        role = ("planner" if "Planner agent" in system
                else "worker" if "Worker agent" in system else "reviewer")
        calls.append((role, content))
        queue = replies[role]
        return (queue.pop(0) if len(queue) > 1 else queue[0]), "fake-model"

    monkeypatch.setattr(agents, "ask_ai_mode", fake_ai_mode)
    server.app.config["TESTING"] = True
    return server.app.test_client(), replies, calls


def create(client, **overrides):
    body = {
        "feature": "student-1",
        "task": "Summarise my Tokyo trip",
        "evidence": [{"label": "trip row", "content": "trip 1: Tokyo, 3-9 May"}],
        "use_rag": False,
    }
    body.update(overrides)
    return client.post("/workflows", json=body)


def test_extract_json_handles_prose_and_fences():
    import agents
    assert agents.extract_json('Here you go:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert agents.extract_json('Sure! {"a": 2} hope that helps') == {"a": 2}
    assert agents.extract_json("no json here") is None


def test_workflow_runs_planner_worker_reviewer_then_waits_for_a_human(app_env):
    client, _, calls = app_env
    response = create(client)
    assert response.status_code == 201
    workflow = response.get_json()

    assert workflow["status"] == "awaiting_human_review"
    assert workflow["final_response"] is None
    assert [role for role, _ in calls] == ["planner", "worker", "reviewer"]
    assert workflow["plan"]["source"] == "model"
    assert workflow["evidence"][0]["id"] == "E1"
    assert workflow["attempts"][0]["review"]["verdict"] == "pass"

    history = client.get(f"/workflows/{workflow['id']}/history").get_json()["history"]
    statuses = [e["detail"]["to"] for e in history if e["event"] == "status"]
    assert statuses == ["planning", "gathering_evidence", "working", "reviewing",
                        "awaiting_human_review"]
    assert [e["actor"] for e in history if e["event"] != "status"] == [
        "student-1", "planner", "server", "worker", "reviewer"]


def test_unparseable_planner_and_reviewer_fall_back_cautiously(app_env):
    client, replies, _ = app_env
    replies["planner"] = ["I think you should look at the trip."]
    replies["reviewer"] = ["Looks good to me!"]
    workflow = create(client).get_json()

    assert workflow["plan"]["source"] == "fallback"
    assert workflow["plan"]["required_evidence"] == ["S1"]
    review = workflow["attempts"][0]["review"]
    assert review["source"] == "fallback"
    assert review["verdict"] == "concerns"


def test_model_pass_is_downgraded_when_nothing_is_cited(app_env):
    client, replies, _ = app_env
    replies["worker"] = ["Your trip is to Tokyo."]
    review = create(client).get_json()["attempts"][0]["review"]
    assert review["verdict"] == "concerns"
    assert any("cites no evidence" in risk for risk in review["risks"])


def test_planner_cannot_select_sources_that_were_not_offered(app_env):
    client, replies, _ = app_env
    replies["planner"] = [GOOD_PLAN.replace('"S1"', '"S1", "S9"')]
    workflow = create(client).get_json()
    assert workflow["plan"]["required_evidence"] == ["S1"]


def test_approve_releases_the_worker_response(app_env):
    client, _, _ = app_env
    workflow = create(client).get_json()
    decided = client.post(f"/workflows/{workflow['id']}/decision",
                          json={"decision": "approve", "reviewer": "Caroline"}).get_json()
    assert decided["status"] == "approved"
    assert decided["final_response"] == "Your trip is to Tokyo [E1]."
    assert decided["decisions"][0]["reviewer"] == "Caroline"


def test_correct_reruns_worker_with_feedback_and_waits_again(app_env):
    client, replies, calls = app_env
    replies["worker"] = ["Your trip is to Tokyo [E1].", "Tokyo, 3-9 May [E1]."]
    workflow = create(client).get_json()

    corrected = client.post(f"/workflows/{workflow['id']}/decision", json={
        "decision": "correct", "reviewer": "Caroline", "feedback": "Include the dates",
    }).get_json()

    assert corrected["status"] == "awaiting_human_review"
    assert corrected["round"] == 2
    assert len(corrected["attempts"]) == 2
    assert corrected["attempts"][1]["worker"]["response"] == "Tokyo, 3-9 May [E1]."
    worker_prompt = [content for role, content in calls if role == "worker"][-1]
    assert "Include the dates" in worker_prompt


def test_corrections_stop_at_the_round_limit(app_env):
    client, _, _ = app_env
    workflow = create(client).get_json()
    url = f"/workflows/{workflow['id']}/decision"
    body = {"decision": "correct", "reviewer": "Caroline", "feedback": "again"}
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json=body).status_code == 409


def test_partial_acceptance_keeps_the_edited_response(app_env):
    client, _, _ = app_env
    workflow = create(client).get_json()
    decided = client.post(f"/workflows/{workflow['id']}/decision", json={
        "decision": "partial", "reviewer": "Caroline", "notes": "dates missing",
        "final_response": "Tokyo trip, dates to be confirmed.",
    }).get_json()
    assert decided["status"] == "partially_accepted"
    assert decided["final_response"] == "Tokyo trip, dates to be confirmed."


def test_reject_releases_nothing_and_closes_the_workflow(app_env):
    client, _, _ = app_env
    workflow = create(client).get_json()
    url = f"/workflows/{workflow['id']}/decision"
    decided = client.post(url, json={"decision": "reject", "reviewer": "Caroline",
                                     "notes": "wrong trip"}).get_json()
    assert decided["status"] == "rejected"
    assert decided["final_response"] is None
    again = client.post(url, json={"decision": "approve", "reviewer": "Caroline"})
    assert again.status_code == 409


@pytest.mark.parametrize("body, message", [
    ({"decision": "maybe", "reviewer": "C"}, "decision must be"),
    ({"decision": "approve"}, "reviewer is required"),
    ({"decision": "correct", "reviewer": "C"}, "needs feedback"),
    ({"decision": "reject", "reviewer": "C"}, "needs notes"),
])
def test_decisions_are_validated(app_env, body, message):
    client, _, _ = app_env
    workflow = create(client).get_json()
    response = client.post(f"/workflows/{workflow['id']}/decision", json=body)
    assert response.status_code == 400
    assert message in response.get_json()["error"]


def test_bad_requests_are_refused(app_env):
    client, _, _ = app_env
    assert create(client, feature="student-9").status_code == 400
    assert create(client, task="").status_code == 400
    assert create(client, task="x" * 1001).status_code == 400
    assert client.get("/workflows/../../etc/passwd").status_code == 404
    assert client.get("/workflows/wf-nope").status_code == 404


def test_ai_mode_down_fails_the_workflow_visibly(app_env, monkeypatch):
    client, _, _ = app_env
    import agents

    def down(*_args, **_kwargs):
        raise agents.AgentError("AI-Mode at http://localhost:5300 did not answer")

    monkeypatch.setattr(agents, "ask_ai_mode", down)
    response = create(client)
    assert response.status_code == 503
    workflow = response.get_json()["workflow"]
    assert workflow["status"] == "failed"
    assert client.get(f"/workflows/{workflow['id']}").get_json()["status"] == "failed"


def test_mcp_refusal_is_kept_as_unavailable_evidence(app_env, monkeypatch):
    client, replies, _ = app_env
    import evidence

    monkeypatch.setattr(evidence, "_fetch_mcp",
                        lambda source: (False, "refused at the owner boundary: no"))
    replies["planner"] = [GOOD_PLAN.replace('"S1"', '"S1", "S2"')]
    workflow = create(client, mcp_calls=[{"tool": "search_flights", "arguments": {}}]).get_json()
    refused = workflow["evidence"][1]
    assert refused["kind"] == "mcp"
    assert refused["ok"] is False
    assert "refused" in refused["content"]
