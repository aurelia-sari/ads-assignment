"""Tests for the deterministic parts of the Release 2 review modes.

Only the code that decides PASS / FAIL is tested here, because that is the part
the review modes rely on the model NOT to do. No service or model is needed:

    ai-services/.venv/bin/python -m pytest ai-services/agentic-loop/tests -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import release2_collectors as r  # noqa: E402
from loop import gate_conflict, release_gate  # noqa: E402


# --- endpoint counting for the Testing Review -----------------------------------

def test_endpoints_are_counted_once_per_route_and_db_setup_is_ignored(tmp_path):
    test_file = tmp_path / "test_x.py"
    test_file.write_text(
        'requests.post(f"{API}/trips", data=x)\n'
        'requests.get(f"{API}/trips/{trip[\'trip_id\']}/days")\n'
        'requests.get(f"{API}/trips/{other[\'trip_id\']}/days")\n'
        'requests.post(f"{DB}/days", json=day)\n'
        'requests.delete(f"{STUDENT1_DB_URL}/trips/{trip_id}")\n'
        'client.get("/guides/1")\n'
        'client.get("/guides/999?x=1")\n'
    )
    assert r._endpoints_in(test_file) == {
        "POST /trips", "GET /trips/<id>/days", "GET /guides/<id>",
    }


def test_ci_test_files_are_read_from_the_pytest_step(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "REPO_ROOT", tmp_path)
    tests = tmp_path / "student-2" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_a.py").write_text("")
    (tests / "test_b.py").write_text("")
    (tests / "helpers.py").write_text("")
    workflow = "run: >-\n          python -m pytest -v\n          student-2/tests\n"
    assert [p.name for p in r._ci_test_files(workflow, 2)] == ["test_a.py", "test_b.py"]
    assert r._ci_test_files("run: python3 scripts/smoke_test.py 2", 2) == []


# --- audit log rules for the Multi-Agent Workflow Review ------------------------

def _workflow(status, attempts=1, decisions=(), final_response=None):
    return {
        "status": status,
        "plan": {"goal": "g"},
        "attempts": [{}] * attempts,
        "final_response": final_response,
        "decisions": list(decisions),
    }


def _history(*events):
    return [{"actor": actor, "event": event, "detail": detail} for actor, event, detail in events]


GOOD_RUN = [
    ("student-1", "created", {}),
    ("planner", "plan", {}),
    ("worker", "response", {}),
    ("reviewer", "review", {}),
]


def test_a_complete_approved_workflow_has_no_audit_problems():
    history = _history(*GOOD_RUN, ("human:Caroline", "decision", {"decision": "approve"}))
    assert r._audit_problems(_workflow("approved", final_response="ok"), history) == []


def test_a_final_status_without_a_human_decision_is_caught():
    problems = r._audit_problems(_workflow("approved", final_response="ok"), _history(*GOOD_RUN))
    assert any("NO human decision" in p for p in problems)


def test_a_status_that_disagrees_with_the_human_decision_is_caught():
    history = _history(*GOOD_RUN, ("human:Caroline", "decision", {"decision": "reject"}))
    problems = r._audit_problems(_workflow("approved", final_response="ok"), history)
    assert any("does not match" in p for p in problems)


def test_work_before_planning_and_missing_reviews_are_caught():
    history = _history(
        ("student-1", "created", {}), ("worker", "response", {}), ("planner", "plan", {}),
    )
    problems = r._audit_problems(_workflow("awaiting_human_review"), history)
    assert any("before the Planner" in p for p in problems)
    assert any("reviewer event" in p for p in problems)


def test_a_response_released_from_a_rejected_workflow_is_caught():
    history = _history(*GOOD_RUN, ("human:Caroline", "decision", {"decision": "reject"}))
    problems = r._audit_problems(_workflow("rejected", final_response="leaked"), history)
    assert any("released" in p for p in problems)


# --- CHECK RESULTS and the release gate -----------------------------------------

def test_check_results_list_failures_first_and_count_them():
    checks = r.Checks()
    checks.add(True, "fine")
    checks.add(False, "watch this", warn=True)
    checks.add(False, "broken")
    report = checks.report(["detail line"])
    head = report.splitlines()
    assert "1 PASS, 1 FAIL, 1 WARN" in head[0]
    assert head[1:4] == ["FAIL - broken", "WARN - watch this", "PASS - fine"]
    assert "DETAIL:\ndetail line" in report
    assert "RELEASE GATE" not in report


def test_release_gate_is_no_go_on_any_failure_and_go_otherwise():
    failing = r.Checks()
    failing.add(True, "a")
    failing.add(False, "b")
    assert release_gate(failing.report([], release_gate=True)) == "NO-GO"

    passing = r.Checks()
    passing.add(True, "a")
    passing.add(False, "only a warning", warn=True)
    assert release_gate(passing.report([], release_gate=True)) == "GO"


def test_a_model_recommendation_against_the_gate_is_overruled():
    evidence = "CHECK RESULTS ...\nRELEASE GATE: NO-GO - 4 cloud requirement(s) failed\n"
    assert "computed gate stands" in gate_conflict(evidence, "**RELEASE RECOMMENDATION:** GO")
    assert gate_conflict(evidence, "RELEASE RECOMMENDATION: NO-GO - frontend down") == ""
    assert gate_conflict(evidence, "no recommendation given") == ""
    assert gate_conflict("no gate here", "RELEASE RECOMMENDATION: GO") == ""
