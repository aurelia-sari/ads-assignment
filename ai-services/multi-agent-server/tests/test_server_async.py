"""Cloud jobs return immediately while the unchanged agent pipeline continues."""

import json
import sys
from pathlib import Path
from threading import Barrier, Event, Thread
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PLAN = json.dumps({
    "goal": "Summarise the trip", "steps": ["Read the trip", "Summarise it"],
    "required_evidence": ["S1"],
    "acceptance_criteria": ["Names the destination", "Cites the evidence"],
})
REVIEW = json.dumps({"verdict": "pass", "criteria": [], "risks": [], "recommendations": []})


@pytest.fixture
def cloud(tmp_path, monkeypatch):
    monkeypatch.setenv("MULTI_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MULTI_AGENT_ASYNC_ENABLED", "true")
    for name in ("server", "agents", "evidence", "store"):
        sys.modules.pop(name, None)
    import agents
    import server
    import store

    roles = []
    gates = []

    def fake_ai(system, content, max_tokens=500):
        role = ("planner" if "Planner agent" in system
                else "worker" if "Worker agent" in system else "reviewer")
        roles.append(role)
        return {"planner": PLAN, "worker": "Your Tokyo trip [E1].", "reviewer": REVIEW}[role], "fake-model"

    monkeypatch.setattr(agents, "ask_ai_mode", fake_ai)
    server.app.config["TESTING"] = True
    env = SimpleNamespace(server=server, agents=agents, store=store,
                          client=server.app.test_client(), roles=roles)

    def hold(role):
        started, released = Event(), Event()
        gates.append(released)
        original = getattr(agents, role)

        def blocked(*args, **kwargs):
            started.set()
            assert released.wait(5), "test did not release the model-call barrier"
            return original(*args, **kwargs)

        monkeypatch.setattr(agents, role, blocked)
        return started, released

    env.hold = hold
    yield env
    for gate in gates:
        gate.set()
    if server._jobs is not None and hasattr(server._jobs, "shutdown"):
        server._jobs.shutdown()


def create(env, **changes):
    payload = {"feature": "student-1", "task": "Summarise my Tokyo trip",
               "evidence": [{"label": "trip", "content": "Tokyo, 3-9 May"}], "use_rag": False}
    payload.update(changes)
    return env.client.post("/workflows", json=payload)


def current(env, workflow_id):
    response = env.client.get(f"/workflows/{workflow_id}")
    assert response.status_code == 200
    return response.get_json()


def test_cloud_creation_returns_saved_id_before_a_model_can_finish(cloud):
    started, release = cloud.hold("plan")
    response = create(cloud)
    assert response.status_code == 202
    accepted = response.get_json()
    assert started.wait(1)
    assert accepted["status"] == "planning"
    assert accepted["plan"] is None
    assert current(cloud, accepted["id"])["status"] == "planning"
    assert cloud.roles == []
    release.set()
    cloud.server._jobs.wait()
    final = current(cloud, accepted["id"])
    assert final["status"] == "awaiting_human_review"
    assert final["final_response"] is None
    assert cloud.roles == ["planner", "worker", "reviewer"]
    history = cloud.store.history(accepted["id"])
    assert [(row["actor"], row["event"]) for row in history if row["event"] != "status"] == [
        ("student-1", "created"), ("planner", "plan"), ("server", "evidence"),
        ("worker", "response"), ("reviewer", "review"),
    ]


def test_accepted_response_is_a_snapshot_even_when_job_finishes_immediately(cloud, monkeypatch):
    class ImmediateQueue:
        def submit(self, callback):
            callback()

    monkeypatch.setattr(cloud.server, "_jobs", ImmediateQueue())
    response = create(cloud)
    accepted = response.get_json()
    assert response.status_code == 202
    assert accepted["status"] == "planning" and accepted["attempts"] == []
    assert current(cloud, accepted["id"])["status"] == "awaiting_human_review"


@pytest.mark.parametrize("failure_kind", ["model", "unexpected"])
def test_background_failures_are_terminal_and_visible_without_request_context(cloud, monkeypatch, failure_kind):
    error = (cloud.agents.AgentError("AI-Mode did not answer") if failure_kind == "model"
             else ValueError("unexpected pipeline failure"))

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(cloud.agents, "plan", fail)
    response = create(cloud)
    assert response.status_code == 202
    cloud.server._jobs.wait()
    workflow = current(cloud, response.get_json()["id"])
    assert workflow["status"] == "failed"
    assert workflow["error"] == str(error)
    assert workflow["final_response"] is None
    assert cloud.store.history(workflow["id"])[-1]["detail"]["to"] == "failed"


def test_correction_returns_immediately_and_duplicate_decisions_are_refused(cloud):
    response = create(cloud)
    cloud.server._jobs.wait()
    wid = response.get_json()["id"]
    started, release = cloud.hold("work")
    url = f"/workflows/{wid}/decision"
    payload = {"decision": "correct", "reviewer": "Cloud reviewer", "feedback": "Include dates"}
    response = cloud.client.post(url, json=payload)
    assert response.status_code == 202
    accepted = response.get_json()
    assert accepted["status"] == "working" and accepted["round"] == 2
    assert accepted["decisions"][-1]["decision"] == "correct"
    assert started.wait(1)
    assert current(cloud, wid)["status"] == "working"
    assert cloud.client.post(url, json=payload).status_code == 409
    assert cloud.client.post(url, json={"decision": "approve", "reviewer": "Other"}).status_code == 409
    release.set()
    cloud.server._jobs.wait()
    workflow = current(cloud, wid)
    assert workflow["status"] == "awaiting_human_review"
    assert workflow["round"] == 2 and len(workflow["attempts"]) == 2
    assert len(workflow["decisions"]) == 1
    assert workflow["attempts"][-1]["worker"]["applied_feedback"] == "Include dates"
    assert workflow["final_response"] is None
    assert cloud.roles == ["planner", "worker", "reviewer", "worker", "reviewer"]


def test_simultaneous_corrections_cannot_both_change_the_round(cloud):
    first = create(cloud)
    cloud.server._jobs.wait()
    wid = first.get_json()["id"]
    started, release = cloud.hold("work")
    barrier = Barrier(3)
    statuses = []

    def correct():
        with cloud.server.app.test_client() as client:
            barrier.wait()
            response = client.post(f"/workflows/{wid}/decision", json={
                "decision": "correct", "reviewer": "Concurrent reviewer", "feedback": "Include dates",
            })
            statuses.append(response.status_code)

    threads = [Thread(target=correct) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    assert started.wait(1)
    assert sorted(statuses) == [202, 409]
    release.set()
    cloud.server._jobs.wait()
    workflow = current(cloud, wid)
    assert workflow["round"] == 2 and len(workflow["decisions"]) == 1


def test_one_worker_and_bounded_queue_fail_overflow_visibly(cloud, monkeypatch):
    monkeypatch.setattr(cloud.server, "MAX_PENDING", 1)
    started, release = cloud.hold("plan")
    first = create(cloud)
    assert started.wait(1)
    second = create(cloud)
    overflow = create(cloud)
    assert first.status_code == second.status_code == 202
    assert overflow.status_code == 503
    rejected = overflow.get_json()["workflow"]
    assert rejected["status"] == "failed"
    assert "queue is full" in rejected["error"]
    assert current(cloud, rejected["id"])["status"] == "failed"
    assert cloud.roles == []
    release.set()
    cloud.server._jobs.wait()
    assert cloud.roles == ["planner", "worker", "reviewer", "planner", "worker", "reviewer"]
    for response in (first, second):
        assert current(cloud, response.get_json()["id"])["status"] == "awaiting_human_review"


def test_queue_refuses_new_work_after_shutdown(cloud):
    cloud.server._job_queue().shutdown()
    response = create(cloud)
    assert response.status_code == 503
    assert response.get_json()["workflow"]["status"] == "failed"
    assert "shutting down" in response.get_json()["detail"]
    # Shutdown is idempotent, including the fixture's orderly teardown.
    cloud.server._jobs.shutdown()


def test_restart_recovery_preserves_reviews_and_final_human_decisions(cloud):
    responses = [create(cloud, task=f"Tokyo task {i}") for i in range(3)]
    cloud.server._jobs.wait()
    ids = [response.get_json()["id"] for response in responses]
    approved = cloud.client.post(f"/workflows/{ids[1]}/decision", json={
        "decision": "approve", "reviewer": "A real human",
    }).get_json()
    interrupted = current(cloud, ids[2])
    interrupted["status"] = "reviewing"
    cloud.store.save(interrupted)
    assert cloud.server.recover_interrupted_workflows() == 1
    assert current(cloud, ids[0])["status"] == "awaiting_human_review"
    assert current(cloud, ids[1]) == approved
    failed = current(cloud, ids[2])
    assert failed["status"] == "failed" and "interrupted" in failed["error"]
    assert failed["final_response"] is None
    assert cloud.server.recover_interrupted_workflows() == 0


def test_recovery_is_disabled_for_normal_local_execution(cloud, monkeypatch):
    response = create(cloud)
    cloud.server._jobs.wait()
    workflow = current(cloud, response.get_json()["id"])
    workflow["status"] = "planning"
    cloud.store.save(workflow)
    monkeypatch.setattr(cloud.server, "ASYNC_ENABLED", False)
    assert cloud.server.recover_interrupted_workflows() == 0
    assert current(cloud, workflow["id"])["status"] == "planning"


def test_cloud_switch_off_retains_synchronous_local_contract(cloud, monkeypatch):
    monkeypatch.setattr(cloud.server, "ASYNC_ENABLED", False)
    response = create(cloud)
    assert response.status_code == 201
    assert response.get_json()["status"] == "awaiting_human_review"
    assert cloud.server._jobs is None
