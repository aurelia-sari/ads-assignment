"""Cloud-only complete Planner/Reviewer JSON keeps real model decisions and local contracts."""

import copy
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests


SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE))
SOURCES = [{"id": "S1", "label": "One offered record"}, {"id": "S3", "label": "Another offered record"}]
PLAN = {"goal": "Recommend one recorded trip", "steps": ["Read S1", "Compare S3"],
        "required_evidence": ["S1", "S3"], "acceptance_criteria": ["Use recorded facts", "Cite usable evidence"]}
EVIDENCE = [{"id": "E1", "ok": True, "label": "Recorded trip", "content": "Trip 17 visits Tokyo."},
            {"id": "E2", "ok": False, "label": "Missing source", "content": "Unavailable."}]
WORKER = {"response": "Trip 17 visits Tokyo [E1].", "model": "live-model"}


@pytest.fixture
def runtime(monkeypatch):
    def load(citations=True, structured=True, reviewer_timeout=None):
        monkeypatch.setenv("CLOUD_CITATION_VALIDATION", str(citations).lower())
        monkeypatch.setenv("CLOUD_STRUCTURED_OUTPUTS_ENABLED", str(structured).lower())
        monkeypatch.delenv("CLOUD_REVIEWER_TIMEOUT_SECONDS", raising=False)
        if reviewer_timeout is not None:
            monkeypatch.setenv("CLOUD_REVIEWER_TIMEOUT_SECONDS", reviewer_timeout)
        spec = importlib.util.spec_from_file_location("structured_agents_test_module", SERVICE / "agents.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load


def transport(module, monkeypatch, generated, model="live-model"):
    response = Mock()
    response.json.return_value = {"answer": generated, "model": model}
    post = Mock(return_value=response)
    monkeypatch.setattr(module.requests, "post", post)
    return post


def review_body(verdict="pass"):
    return {"verdict": verdict,
            "criteria": {f"C{number}": {"criterion": value, "met": verdict == "pass", "note": "A real model assessment."}
                         for number, value in enumerate(PLAN["acceptance_criteria"], start=1)},
            "risks": [] if verdict == "pass" else ["The model found a concern."],
            "recommendations": ["Check the recorded facts before release."]}


def planner(module, sources=SOURCES):
    return module.plan("generic-feature", "Recommend one trip from the offered records.", sources)


def reviewer(module, **kwargs):
    return module.review("Recommend one trip from the evidence.", kwargs.get("plan", PLAN),
                         kwargs.get("evidence", EVIDENCE), kwargs.get("worker", WORKER))


def test_cloud_planner_sends_a_complete_bounded_schema_and_keeps_actual_model_values(runtime, monkeypatch):
    module = runtime()
    raw = json.dumps(PLAN)
    post = transport(module, monkeypatch, raw)
    result = planner(module)
    assert result == {"source": "model", "model": "live-model", **PLAN, "raw": raw}
    assert post.call_count == 1 and post.call_args.kwargs["timeout"] == module.TIMEOUT == 180
    payload = post.call_args.kwargs["json"]
    assert payload["max_tokens"] == 900
    response_format = payload["response_format"]
    assert response_format["type"] == "json_schema" and response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(PLAN) == set(schema["required"])
    fields = schema["properties"]
    assert fields["goal"]["maxLength"] == 300
    assert fields["steps"]["minItems"] == 1 and fields["steps"]["maxItems"] == 5
    assert fields["steps"]["items"]["maxLength"] == 160
    assert fields["required_evidence"]["items"]["enum"] == ["S1", "S3"]
    assert fields["required_evidence"]["minItems"] == 1 and fields["required_evidence"]["maxItems"] == 2
    assert fields["acceptance_criteria"]["maxItems"] == 4
    assert fields["acceptance_criteria"]["items"]["maxLength"] == 200
    assert "Output JSON Schema:" in payload["question"]
    assert "One offered record" in payload["question"] and "Another offered record" in payload["question"]
    assert payload["system"].startswith(module.load_prompt("planner_prompt.txt"))
    assert "pattern" not in json.dumps(schema)


def test_planner_without_sources_accepts_only_an_empty_required_evidence_array(runtime, monkeypatch):
    module = runtime()
    generated = {**PLAN, "required_evidence": []}
    post = transport(module, monkeypatch, json.dumps(generated))
    assert planner(module, sources=[])["source"] == "model"
    reference = post.call_args.kwargs["json"]["response_format"]["json_schema"]["schema"]["properties"]["required_evidence"]
    assert reference["minItems"] == reference["maxItems"] == 0
    assert "enum" not in reference["items"]
    post.return_value.json.return_value["answer"] = json.dumps(PLAN)
    with pytest.raises(module.AgentError, match="invalid or incomplete JSON"):
        planner(module, sources=[])


@pytest.mark.parametrize("patch", [
    {"goal": ""}, {"goal": "x" * 301}, {"goal": 7}, {"goal": "   "},
    {"steps": []}, {"steps": ["x"] * 6}, {"steps": ["x" * 161]}, {"steps": [1]},
    {"steps": ["   "]}, {"required_evidence": []}, {"required_evidence": ["S99"]},
    {"required_evidence": ["S1", "S3", "S1"]}, {"required_evidence": ["E1"]},
    {"acceptance_criteria": []}, {"acceptance_criteria": ["x"] * 5},
    {"acceptance_criteria": ["x" * 201]}, {"extra": "not model contract"},
])
def test_invalid_structured_plan_fails_without_fabricating_a_fallback_plan(runtime, monkeypatch, patch):
    module = runtime()
    post = transport(module, monkeypatch, json.dumps({**PLAN, **patch}))
    with pytest.raises(module.AgentError, match="Planner structured generation"):
        planner(module)
    assert post.call_count == 1


@pytest.mark.parametrize("raw", [None, 7, {}, [], "", "not json", "null", "[]", "{}",
                                json.dumps(PLAN)[:-1], "```json\n" + json.dumps(PLAN) + "\n```",
                                json.dumps(PLAN) + "\nExtra explanation."])
def test_cloud_planner_does_not_extract_or_complete_bad_json_as_a_model_plan(runtime, monkeypatch, raw):
    module = runtime()
    post = transport(module, monkeypatch, raw)
    with pytest.raises(module.AgentError, match="invalid or incomplete JSON"):
        planner(module)
    assert post.call_count == 1


@pytest.mark.parametrize("citations,structured", [(False, False), (False, True), (True, False)])
def test_planner_legacy_flags_keep_original_signature_prompt_budget_and_parser(runtime, monkeypatch, citations, structured):
    module = runtime(citations, structured)
    calls = []

    def legacy(system, content, max_tokens=500):
        calls.append((system, content, max_tokens))
        return "```json\n" + json.dumps(PLAN) + "\n```", "legacy-model"

    monkeypatch.setattr(module, "ask_ai_mode", legacy)
    result = planner(module)
    assert result["source"] == "model" and result["model"] == "legacy-model"
    assert len(calls) == 1 and calls[0][2] == 400
    assert calls[0][0] == module.load_prompt("planner_prompt.txt")
    assert "Output JSON Schema:" not in calls[0][1]


def test_local_invalid_planner_response_retains_the_existing_honest_fallback(runtime, monkeypatch):
    module = runtime(False, False)
    post = transport(module, monkeypatch, "An unstructured local response.")
    result = planner(module)
    assert result["source"] == "fallback" and result["raw"] == "An unstructured local response."
    assert result["required_evidence"] == ["S1", "S3"]
    assert post.call_args.kwargs["json"]["max_tokens"] == 400
    assert post.call_args.kwargs["timeout"] == 180


def test_cloud_reviewer_schema_evaluates_each_original_criterion_without_changing_timeouts(runtime, monkeypatch):
    module = runtime(reviewer_timeout="360")
    body = review_body()
    raw = json.dumps(body)
    post = transport(module, monkeypatch, raw)
    result = reviewer(module)
    assert result["source"] == "model" and result["raw"] == raw
    assert result["criteria"] == list(body["criteria"].values()) and result["recommendations"] == body["recommendations"]
    assert post.call_count == 1 and post.call_args.kwargs["timeout"] == 360
    payload = post.call_args.kwargs["json"]
    assert payload["max_tokens"] == 1200
    schema = payload["response_format"]["json_schema"]["schema"]
    assert set(schema["required"]) == {"verdict", "criteria", "risks", "recommendations"}
    assert schema["additionalProperties"] is False
    fields = schema["properties"]
    assert fields["verdict"]["enum"] == ["pass", "concerns", "fail"]
    assert fields["criteria"]["type"] == "object"
    assert fields["criteria"]["required"] == ["C1", "C2"]
    assert fields["criteria"]["additionalProperties"] is False
    for number, expected in enumerate(PLAN["acceptance_criteria"], start=1):
        criterion = fields["criteria"]["properties"][f"C{number}"]
        assert criterion["properties"]["criterion"]["enum"] == [expected]
        assert criterion["properties"]["met"] == {"type": "boolean"}
        assert criterion["properties"]["note"]["maxLength"] == 100
    for name in ("risks", "recommendations"):
        assert fields[name]["maxItems"] == 6 and fields[name]["items"]["maxLength"] == 140
    assert "exactly once" in payload["system"]
    assert "Output JSON Schema:" in payload["question"]
    assert "Trip 17 visits Tokyo." in payload["question"]
    assert "Worker response:\nTrip 17 visits Tokyo [E1]." in payload["question"]
    assert "pattern" not in json.dumps(schema)


@pytest.mark.parametrize("verdict", ["pass", "concerns", "fail"])
def test_structured_reviewer_preserves_the_actual_model_verdict_and_boolean_assessments(runtime, monkeypatch, verdict):
    module = runtime()
    body = review_body(verdict)
    transport(module, monkeypatch, json.dumps(body))
    result = reviewer(module)
    assert result["verdict"] == verdict and result["source"] == "model"
    assert result["criteria"] == list(body["criteria"].values()) and result["risks"] == body["risks"]
    assert result["checks"] == {"cited": ["E1"], "risks": []}


@pytest.mark.parametrize("response", ["No citation.", "Tokyo [E99].", "Tokyo [E2]."])
def test_deterministic_risks_still_override_a_structured_model_pass(runtime, monkeypatch, response):
    module = runtime()
    transport(module, monkeypatch, json.dumps(review_body("pass")))
    result = reviewer(module, worker={"response": response})
    assert result["source"] == "model" and result["verdict"] == "concerns"
    assert result["checks"]["risks"] and result["risks"] == result["checks"]["risks"]


@pytest.mark.parametrize("patch", [
    {"verdict": "approve"}, {"verdict": True}, {"criteria": []},
    {"criteria": [{"criterion": PLAN["acceptance_criteria"][0], "met": True, "note": "A"}] * 2},
    {"criteria": [{"criterion": "Invented criterion", "met": True, "note": "A"}] * 2},
    {"criteria": [{"criterion": value, "met": "false", "note": "A"} for value in PLAN["acceptance_criteria"]]},
    {"criteria": [{"criterion": value, "met": 1, "note": "A"} for value in PLAN["acceptance_criteria"]]},
    {"criteria": [{"criterion": value, "met": True, "note": "A" * 101} for value in PLAN["acceptance_criteria"]]},
    {"criteria": [{"criterion": value, "met": True} for value in PLAN["acceptance_criteria"]]},
    {"criteria": [{"criterion": value, "met": True, "note": "A", "extra": "x"} for value in PLAN["acceptance_criteria"]]},
    {"risks": ["A"] * 7}, {"risks": ["A" * 141]}, {"risks": [None]},
    {"recommendations": ["A"] * 7}, {"recommendations": ["A" * 141]}, {"recommendations": "Not an array"},
    {"extra": "Not in model contract"},
])
def test_invalid_model_review_fails_without_coercing_fields_or_replacing_a_verdict(runtime, monkeypatch, patch):
    module = runtime()
    post = transport(module, monkeypatch, json.dumps({**review_body(), **patch}))
    with pytest.raises(module.AgentError, match="Reviewer structured generation"):
        reviewer(module)
    assert post.call_count == 1


@pytest.mark.parametrize("raw", [None, {}, [], 3, "not json", "null", "[]", "{}", json.dumps(review_body())[:-1],
                                "```json\n" + json.dumps(review_body()) + "\n```", json.dumps(review_body()) + " extra"])
def test_structured_review_does_not_extract_bad_or_incomplete_json_as_a_model_review(runtime, monkeypatch, raw):
    module = runtime()
    post = transport(module, monkeypatch, raw)
    with pytest.raises(module.AgentError, match="invalid or incomplete JSON"):
        reviewer(module)
    assert post.call_count == 1


@pytest.mark.parametrize("criteria", [[], ["A"] * 5, [""], [1]])
def test_structured_reviewer_rejects_missing_original_criteria_before_generation(runtime, monkeypatch, criteria):
    module = runtime()
    post = transport(module, monkeypatch, json.dumps(review_body()))
    with pytest.raises(module.AgentError, match="1-4 original acceptance criteria"):
        reviewer(module, plan={**PLAN, "acceptance_criteria": criteria})
    post.assert_not_called()


@pytest.mark.parametrize("citations,structured", [(False, False), (False, True), (True, False)])
def test_legacy_reviewer_keeps_original_signature_prompt_budget_and_parser(runtime, monkeypatch, citations, structured):
    module = runtime(citations, structured)
    calls = []

    def legacy(system, content, max_tokens=500):
        calls.append((system, content, max_tokens))
        legacy_body = review_body("concerns")
        legacy_body["criteria"] = list(legacy_body["criteria"].values())
        return "```json\n" + json.dumps(legacy_body) + "\n```", "legacy-model"

    monkeypatch.setattr(module, "ask_ai_mode", legacy)
    result = reviewer(module)
    assert result["source"] == "model" and result["verdict"] == "concerns"
    assert result["model"] == "legacy-model"
    assert len(calls) == 1 and calls[0][2] == 500
    assert calls[0][0] == module.load_prompt("reviewer_prompt.txt")
    assert "Output JSON Schema:" not in calls[0][1]


def test_legacy_reviewer_fallback_remains_explicitly_unreviewed(runtime, monkeypatch):
    module = runtime(False, False, reviewer_timeout="360")
    post = transport(module, monkeypatch, "Unstructured local review.")
    result = reviewer(module)
    assert result["source"] == "fallback" and result["verdict"] == "concerns"
    assert result["criteria"] == [] and "unreviewed" in result["risks"][0]
    assert post.call_args.kwargs["timeout"] == 180


@pytest.mark.parametrize("agent", ["planner", "reviewer"])
@pytest.mark.parametrize("error", [requests.Timeout("Too slow"), requests.HTTPError("503 Backend unavailable")])
def test_structured_transport_failures_propagate_without_retry_or_fake_model_result(runtime, monkeypatch, agent, error):
    module = runtime(reviewer_timeout="360")
    post = Mock(side_effect=error)
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(module.AgentError, match="structured generation failed"):
        planner(module) if agent == "planner" else reviewer(module)
    assert post.call_count == 1


@pytest.mark.parametrize("configured", [None, "360"])
def test_cloud_reviewer_timeout_is_separate_from_the_unchanged_planner_timeout(runtime, monkeypatch, configured):
    module = runtime(reviewer_timeout=configured)
    response = Mock()
    response.json.side_effect = [{"answer": json.dumps(PLAN), "model": "live-model"},
                                 {"answer": json.dumps(review_body()), "model": "live-model"}]
    post = Mock(return_value=response)
    monkeypatch.setattr(module.requests, "post", post)
    planner(module)
    reviewer(module)
    assert [call.kwargs["timeout"] for call in post.call_args_list] == [180, 360 if configured else 180]
    assert [call.kwargs["json"]["max_tokens"] for call in post.call_args_list] == [900, 1200]


@pytest.mark.parametrize("model", [None, "", "another-real-model"])
def test_structured_agents_preserve_model_metadata_without_placeholder_substitution(runtime, monkeypatch, model):
    module = runtime()
    post = transport(module, monkeypatch, json.dumps(PLAN), model=model)
    assert planner(module)["model"] == model
    post.return_value.json.return_value["answer"] = json.dumps(review_body())
    assert reviewer(module)["model"] == model


@pytest.mark.parametrize("field,value", [
    ("criterion", "An invented criterion"), ("criterion", PLAN["acceptance_criteria"][1]),
    ("met", "true"), ("met", 1), ("note", None), ("note", "x" * 101),
    ("extra", "Unrequested field"),
])
def test_each_assigned_criterion_rejects_invalid_model_fields_without_coercion(runtime, monkeypatch, field, value):
    module = runtime()
    body = review_body()
    body["criteria"]["C1"][field] = value
    transport(module, monkeypatch, json.dumps(body))
    with pytest.raises(module.AgentError, match="invalid or incomplete JSON"):
        reviewer(module)


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate"])
def test_criterion_object_keys_and_single_value_enums_prevent_duplicate_or_missing_checks(runtime, monkeypatch, change):
    module = runtime()
    body = review_body()
    if change == "missing":
        body["criteria"].pop("C2")
    elif change == "extra":
        body["criteria"]["C3"] = copy.deepcopy(body["criteria"]["C1"])
    else:
        body["criteria"]["C2"] = copy.deepcopy(body["criteria"]["C1"])
    transport(module, monkeypatch, json.dumps(body))
    with pytest.raises(module.AgentError, match="invalid or incomplete JSON"):
        reviewer(module)


def test_model_criterion_object_is_normalized_in_plan_order_without_changing_assessments(runtime, monkeypatch):
    module = runtime()
    body = review_body("concerns")
    body["criteria"]["C1"]["met"] = False
    body["criteria"]["C2"]["met"] = True
    expected = copy.deepcopy(list(body["criteria"].values()))
    body["criteria"] = {"C2": body["criteria"]["C2"], "C1": body["criteria"]["C1"]}
    raw = json.dumps(body)
    transport(module, monkeypatch, raw)
    result = reviewer(module)
    assert result["criteria"] == expected
    assert result["raw"] == raw and result["verdict"] == "concerns"


def test_six_actual_model_risks_and_recommendations_are_preserved(runtime, monkeypatch):
    module = runtime()
    body = review_body("concerns")
    body["risks"] = [f"Model risk {number}." for number in range(6)]
    body["recommendations"] = [f"Model recommendation {number}." for number in range(6)]
    transport(module, monkeypatch, json.dumps(body))
    result = reviewer(module)
    assert result["risks"] == body["risks"]
    assert result["recommendations"] == body["recommendations"]
