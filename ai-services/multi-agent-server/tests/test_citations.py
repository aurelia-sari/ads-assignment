"""Cloud Worker repairs must be model-authored, bounded and evidence-valid."""

import copy
import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests


SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE))

PLAN = {"goal": "Choose one available trip", "steps": ["Read its destination", "Cite the evidence"]}
EVIDENCE = [
    {"id": "E1", "ok": True, "label": "Available trip", "content": "Trip 17 visits Tokyo."},
    {"id": "E2", "ok": False, "label": "Another source", "content": "Source unavailable."},
]


@pytest.fixture
def load_runtime(monkeypatch):
    def load(enabled=False, worker_timeout=None, reviewer_timeout=None):
        monkeypatch.delenv("CLOUD_WORKER_TIMEOUT_SECONDS", raising=False)
        if worker_timeout is not None:
            monkeypatch.setenv("CLOUD_WORKER_TIMEOUT_SECONDS", worker_timeout)
        monkeypatch.delenv("CLOUD_REVIEWER_TIMEOUT_SECONDS", raising=False)
        if reviewer_timeout is not None:
            monkeypatch.setenv("CLOUD_REVIEWER_TIMEOUT_SECONDS", reviewer_timeout)
        if enabled:
            monkeypatch.setenv("CLOUD_CITATION_VALIDATION", "true")
        else:
            monkeypatch.delenv("CLOUD_CITATION_VALIDATION", raising=False)
        spec = importlib.util.spec_from_file_location("citation_test_agents", SERVICE / "agents.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load


def worker(runtime, **kwargs):
    return runtime.work("Recommend my trip", PLAN, EVIDENCE, **kwargs)


def test_local_default_keeps_original_prompt_timeout_call_count_and_fake_signature(load_runtime, monkeypatch):
    runtime = load_runtime(worker_timeout="360")
    calls = []

    def legacy_fake(system, content, max_tokens=500):
        calls.append((system, content, max_tokens))
        return "A legacy answer with no citation.", "local-model"

    monkeypatch.setattr(runtime, "ask_ai_mode", legacy_fake)
    result = worker(runtime)
    assert runtime.CLOUD_CITATION_VALIDATION is False
    assert result == {"model": "local-model", "response": "A legacy answer with no citation.",
                      "applied_feedback": None}
    assert len(calls) == 1
    assert calls[0][0] == runtime.load_prompt("worker_prompt.txt")
    assert calls[0][2] == 450
    assert "Cloud citation validation" not in calls[0][0]


def test_cloud_valid_first_answer_is_unchanged_and_only_called_once(load_runtime, monkeypatch):
    runtime = load_runtime(True)
    generated = "Tokyo is the destination of trip 17 [E1]."
    generate = Mock(return_value=(generated, "actual-model"))
    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    result = worker(runtime)
    assert result == {"model": "actual-model", "response": generated, "applied_feedback": None}
    assert generate.call_count == 1
    system, content = generate.call_args.args
    assert "ONLY permitted evidence citations are [E1]" in system
    cloud_rules = system.split("\n\nCloud citation validation:", 1)[1]
    assert "[E2]" not in cloud_rules
    assert "Recommend my trip" in content and "Trip 17 visits Tokyo." in content
    assert generate.call_args.kwargs["max_tokens"] == 450
    assert 0 < generate.call_args.kwargs["timeout"] <= min(runtime.TIMEOUT, 165)


@pytest.mark.parametrize("invalid", [
    "The trip visits Tokyo.", "", "The trip visits Tokyo [E99].",
    "Tokyo [E1] and unavailable information [E2].", "Tokyo [E1] and another claim [E99].",
    "Tokyo [E1, E1].", "Tokyo [E1] and another fact [E1, E1].",
    "Tokyo [E1] plus source [S1].", "Tokyo [E1] plus numeric source [1].", "Tokyo [e1].",
    "Tokyo [E1] and malformed [1, x].", "Tokyo [E1] and malformed [1 x].",
])
def test_missing_unknown_mixed_unavailable_or_noncanonical_references_need_one_real_repair(
        load_runtime, monkeypatch, invalid):
    runtime = load_runtime(True)
    corrected = "The available trip visits Tokyo [E1]."
    generate = Mock(side_effect=[(invalid, "first-model"), (corrected, "repair-model")])
    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    result = worker(runtime)
    assert result["response"] == corrected and result["model"] == "repair-model"
    assert result["applied_feedback"] is None
    assert generate.call_count == 2
    original = generate.call_args_list[0].args[1]
    repair = generate.call_args_list[1].args[1]
    assert repair.startswith(original)
    assert invalid in repair
    assert "Automatic citation validation (not human feedback)" in repair
    assert "Permitted citations: [E1]." in repair


def test_repair_preserves_original_task_plan_evidence_and_actual_human_feedback(load_runtime, monkeypatch):
    runtime = load_runtime(True)
    generate = Mock(side_effect=[("Tokyo without a reference.", "model"), ("Tokyo [E1].", "model")])
    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    result = worker(runtime, feedback="Include trip 17, in one sentence.", previous="An old answer [E1].")
    assert result["applied_feedback"] == "Include trip 17, in one sentence."
    original = generate.call_args_list[0].args[1]
    repaired = generate.call_args_list[1].args[1]
    for content in (original, repaired):
        assert "Task: Recommend my trip" in content
        assert "Plan goal: Choose one available trip" in content
        assert "Trip 17 visits Tokyo." in content
        assert "Your previous response:\nAn old answer [E1]." in content
        assert "Human reviewer feedback to apply:\nInclude trip 17, in one sentence." in content
    assert repaired.startswith(original)


@pytest.mark.parametrize("invalid", ["Tokyo [E99].", "Tokyo [E1] and malformed [1, x]."])
def test_persistently_invalid_answer_fails_instead_of_appending_or_remapping_citations(
        load_runtime, monkeypatch, invalid):
    runtime = load_runtime(True)
    generate = Mock(return_value=(invalid, "model"))
    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    with pytest.raises(runtime.AgentError, match="failed after one repair"):
        worker(runtime)
    assert generate.call_count == 2


def test_no_usable_evidence_fails_before_requesting_a_fabricated_reference(load_runtime, monkeypatch):
    runtime = load_runtime(True)
    generate = Mock()
    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    for evidence in ([], [{**item, "ok": False} for item in EVIDENCE]):
        with pytest.raises(runtime.AgentError, match="No usable evidence"):
            runtime.work("Recommend my trip", PLAN, evidence)
    generate.assert_not_called()


def test_two_available_ids_may_be_cited_separately_without_repair(load_runtime, monkeypatch):
    runtime = load_runtime(True)
    evidence = copy.deepcopy(EVIDENCE)
    evidence[1].update(ok=True, content="Trip 18 visits Osaka.")
    generate = Mock(return_value=("Tokyo [E1]. Osaka [E2].", "model"))
    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    assert runtime.work("Summarise trips", PLAN, evidence)["response"] == "Tokyo [E1]. Osaka [E2]."
    assert generate.call_count == 1
    assert "[E1], [E2]" in generate.call_args.args[0]


def test_repair_uses_the_remaining_original_timeout_budget(load_runtime, monkeypatch):
    runtime = load_runtime(True)
    now = [10.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runtime, "TIMEOUT", 100)
    calls = []

    def generate(system, content, max_tokens=500, timeout=None):
        calls.append(timeout)
        if len(calls) == 1:
            now[0] += 70
            return "Tokyo has no reference.", "model"
        now[0] += 5
        return "Tokyo [E1].", "model"

    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    assert worker(runtime)["response"] == "Tokyo [E1]."
    assert calls == [100, 30]


def test_cloud_360_second_budget_is_shared_by_initial_generation_and_repair(load_runtime, monkeypatch):
    runtime = load_runtime(True, worker_timeout="360")
    now = [0.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])
    timeouts = []

    def post(url, **kwargs):
        timeouts.append(kwargs["timeout"])
        now[0] += 200 if len(timeouts) == 1 else 150
        reply = Mock()
        reply.json.return_value = {
            "answer": "No citation." if len(timeouts) == 1 else "Tokyo [E1].",
            "model": "actual-model",
        }
        return reply

    monkeypatch.setattr(runtime.requests, "post", post)
    assert worker(runtime)["response"] == "Tokyo [E1]."
    assert timeouts == [360, 160]
    assert runtime.TIMEOUT == 180


def test_cloud_valid_first_answer_can_finish_after_the_old_165_second_limit(load_runtime, monkeypatch):
    runtime = load_runtime(True, worker_timeout="360")
    now = [0.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])
    calls = []

    def generate(system, content, max_tokens=500, timeout=None):
        calls.append(timeout)
        now[0] += 200
        return "Tokyo [E1].", "model"

    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    assert worker(runtime)["response"] == "Tokyo [E1]."
    assert calls == [360]


def test_cloud_worker_budget_keeps_planner_and_reviewer_timeouts_unchanged(load_runtime, monkeypatch):
    runtime = load_runtime(True, worker_timeout="360")
    reply = Mock()
    reply.json.return_value = {"answer": "{}", "model": "model"}
    post = Mock(return_value=reply)
    monkeypatch.setattr(runtime.requests, "post", post)
    runtime.plan("student-3", "Recommend my trip", [])
    runtime.review("Recommend my trip", {**PLAN, "acceptance_criteria": ["Cite usable evidence"]},
                   EVIDENCE, {"response": "Tokyo [E1]."})
    assert [call.kwargs["timeout"] for call in post.call_args_list] == [180, 180]


def test_cloud_reviewer_360_seconds_keeps_planner_and_worker_budgets_separate(load_runtime, monkeypatch):
    runtime = load_runtime(True, worker_timeout="360", reviewer_timeout="360")
    reply = Mock()
    reply.json.return_value = {"answer": "Tokyo [E1].", "model": "actual-model"}
    post = Mock(return_value=reply)
    monkeypatch.setattr(runtime.requests, "post", post)
    now = [0.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])
    runtime.plan("student-3", "Recommend my trip", [])
    worker(runtime)
    runtime.review("Recommend my trip", {**PLAN, "acceptance_criteria": ["Cite usable evidence"]},
                   EVIDENCE, {"response": "Tokyo [E1]."})
    assert [call.kwargs["timeout"] for call in post.call_args_list] == [180, 360, 360]


@pytest.mark.parametrize("configured", [None, "360", "invalid"])
def test_local_reviewer_keeps_180_seconds_even_with_cloud_setting(load_runtime, monkeypatch, configured):
    runtime = load_runtime(reviewer_timeout=configured)
    reply = Mock()
    reply.json.return_value = {"answer": "{}", "model": "local-model"}
    post = Mock(return_value=reply)
    monkeypatch.setattr(runtime.requests, "post", post)
    runtime.review("Recommend my trip", {**PLAN, "acceptance_criteria": []},
                   EVIDENCE, {"response": "Tokyo [E1]."})
    assert post.call_count == 1
    assert post.call_args.kwargs["timeout"] == 180


@pytest.mark.parametrize("cloud_enabled, configured", [(False, None), (False, "360"), (True, None)])
def test_local_or_unconfigured_reviewer_keeps_legacy_signature_and_prompt(
        load_runtime, monkeypatch, cloud_enabled, configured):
    runtime = load_runtime(cloud_enabled, reviewer_timeout=configured)
    calls = []

    def legacy_fake(system, content, max_tokens=500):
        calls.append((system, content, max_tokens))
        return '{"verdict": "pass", "criteria": [], "risks": [], "recommendations": []}', "model"

    monkeypatch.setattr(runtime, "ask_ai_mode", legacy_fake)
    result = runtime.review("Recommend my trip", {**PLAN, "acceptance_criteria": ["Cite usable evidence"]},
                            EVIDENCE, {"response": "Tokyo [E1]."})
    assert len(calls) == 1
    assert calls[0][0] == runtime.load_prompt("reviewer_prompt.txt")
    assert "Task: Recommend my trip" in calls[0][1]
    assert "Worker response:\nTokyo [E1]." in calls[0][1]
    assert calls[0][2] == 500
    assert result["verdict"] == "pass"


def test_cloud_reviewer_timeout_does_not_retry_or_change_the_review_prompt(load_runtime, monkeypatch):
    runtime = load_runtime(True, reviewer_timeout="360")
    post = Mock(side_effect=requests.Timeout("reviewer timed out"))
    monkeypatch.setattr(runtime.requests, "post", post)
    with pytest.raises(runtime.AgentError, match="did not answer"):
        runtime.review("Recommend my trip", {**PLAN, "acceptance_criteria": []},
                       EVIDENCE, {"response": "Tokyo [E1]."})
    assert post.call_count == 1
    assert post.call_args.kwargs["timeout"] == 360
    assert post.call_args.kwargs["json"]["system"] == runtime.load_prompt("reviewer_prompt.txt")
    assert post.call_args.kwargs["json"]["max_tokens"] == 500


@pytest.mark.parametrize("value", ["", "0", "-1", "invalid", "nan", "inf"])
def test_invalid_cloud_reviewer_timeout_fails_before_requesting_generation(load_runtime, monkeypatch, value):
    runtime = load_runtime(True, reviewer_timeout=value)
    generate = Mock()
    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    with pytest.raises(runtime.AgentError, match="CLOUD_REVIEWER_TIMEOUT_SECONDS must be a positive integer"):
        runtime.review("Recommend my trip", {**PLAN, "acceptance_criteria": []},
                       EVIDENCE, {"response": "Tokyo [E1]."})
    generate.assert_not_called()


@pytest.mark.parametrize("elapsed", [(360,), (200, 161)])
def test_cloud_360_second_deadline_is_enforced_across_both_generations(
        load_runtime, monkeypatch, elapsed):
    runtime = load_runtime(True, worker_timeout="360")
    now = [0.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])
    calls = []

    def generate(system, content, max_tokens=500, timeout=None):
        calls.append(timeout)
        now[0] += elapsed[len(calls) - 1]
        return ("No citation." if len(calls) == 1 else "Tokyo [E1]."), "model"

    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    with pytest.raises(runtime.AgentError, match="generation deadline"):
        worker(runtime)
    assert calls == ([360] if len(elapsed) == 1 else [360, 160])


@pytest.mark.parametrize("timeout_at", [1, 2])
def test_cloud_transport_timeout_is_not_retried_with_the_longer_budget(
        load_runtime, monkeypatch, timeout_at):
    runtime = load_runtime(True, worker_timeout="360")
    reply = Mock()
    reply.json.return_value = {"answer": "No citation.", "model": "model"}
    effects = [reply] * (timeout_at - 1) + [requests.Timeout("model timed out")]
    post = Mock(side_effect=effects)
    monkeypatch.setattr(runtime.requests, "post", post)
    with pytest.raises(runtime.AgentError, match="did not answer"):
        worker(runtime)
    assert post.call_count == timeout_at


@pytest.mark.parametrize("value", ["0", "-1", "invalid", "nan", "inf"])
def test_invalid_cloud_worker_budget_fails_before_requesting_generation(load_runtime, monkeypatch, value):
    runtime = load_runtime(True, worker_timeout=value)
    generate = Mock()
    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    with pytest.raises(runtime.AgentError, match="CLOUD_WORKER_TIMEOUT_SECONDS must be a positive integer"):
        worker(runtime)
    generate.assert_not_called()


def test_first_generation_exhausting_deadline_does_not_start_a_repair(load_runtime, monkeypatch):
    runtime = load_runtime(True)
    now = [0.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])
    calls = []

    def generate(system, content, max_tokens=500, timeout=None):
        calls.append(timeout)
        now[0] += min(runtime.TIMEOUT, 165)
        return "No reference.", "model"

    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    with pytest.raises(runtime.AgentError, match="generation deadline"):
        worker(runtime)
    assert len(calls) == 1


def test_late_repair_is_not_returned_after_the_overall_generation_deadline(load_runtime, monkeypatch):
    runtime = load_runtime(True)
    now = [0.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: now[0])
    calls = []

    def generate(system, content, max_tokens=500, timeout=None):
        calls.append(timeout)
        now[0] += 100
        return ("No reference." if len(calls) == 1 else "Tokyo [E1]."), "model"

    monkeypatch.setattr(runtime, "ask_ai_mode", generate)
    with pytest.raises(runtime.AgentError, match="generation deadline"):
        worker(runtime)
    assert len(calls) == 2


@pytest.mark.parametrize("error", [requests.Timeout("model timed out"), requests.HTTPError("HTTP 503")])
def test_transport_errors_do_not_trigger_a_second_model_generation(load_runtime, monkeypatch, error):
    runtime = load_runtime(True)
    post = Mock(side_effect=error)
    monkeypatch.setattr(runtime.requests, "post", post)
    with pytest.raises(runtime.AgentError, match="did not answer"):
        worker(runtime)
    assert post.call_count == 1


@pytest.mark.parametrize("model", [None, "", "other-model"])
def test_returned_model_metadata_is_not_fabricated_or_replaced(load_runtime, monkeypatch, model):
    runtime = load_runtime(True)
    monkeypatch.setattr(runtime, "ask_ai_mode", Mock(return_value=("Tokyo [E1].", model)))
    assert worker(runtime)["model"] == model


def test_ask_ai_mode_keeps_default_timeout_and_accepts_the_cloud_remaining_budget(load_runtime, monkeypatch):
    runtime = load_runtime()
    result = Mock()
    result.json.return_value = {"answer": "Tokyo [E1].", "model": "model"}
    post = Mock(return_value=result)
    monkeypatch.setattr(runtime.requests, "post", post)
    runtime.ask_ai_mode("System", "Task", max_tokens=450)
    assert post.call_args.kwargs["timeout"] == runtime.TIMEOUT
    runtime.ask_ai_mode("System", "Task", max_tokens=450, timeout=12.5)
    assert post.call_args.kwargs["timeout"] == 12.5
    assert post.call_count == 2
    assert result.raise_for_status.call_count == 2
