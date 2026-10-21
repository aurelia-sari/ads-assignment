"""Opt-in model-authored answers and citations preserve real evidence and local calls."""

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests


SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE))
PLAN = {"goal": "Choose a trip from the supplied facts",
        "steps": ["Read the destination", "Explain the choice using its evidence"],
        "acceptance_criteria": ["Cite actual evidence"]}
EVIDENCE = [
    {"id": "E1", "ok": True, "label": "Available trip", "content": "Trip 17 visits Tokyo."},
    {"id": "E2", "ok": False, "label": "Unavailable source", "content": "Source unavailable."},
    {"id": "E3", "ok": True, "label": "Another trip", "content": "Trip 18 visits Osaka."},
]


@pytest.fixture
def runtime(monkeypatch):
    def load(citations=True, structured=True, budget="360"):
        monkeypatch.setenv("CLOUD_CITATION_VALIDATION", str(citations).lower())
        monkeypatch.setenv("CLOUD_STRUCTURED_OUTPUTS_ENABLED", str(structured).lower())
        monkeypatch.setenv("CLOUD_WORKER_TIMEOUT_SECONDS", budget)
        spec = importlib.util.spec_from_file_location("structured_worker_test_agents", SERVICE / "agents.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load


def invoke(module, **kwargs):
    return module.work("Recommend one trip", PLAN, EVIDENCE, **kwargs)


def envelope(answer, citation=None):
    """Encode fixture model fields, without changing the fixture's answer text."""
    first = re.search(r"\[E\d+\]", answer)
    selected = citation if citation is not None else first.group() if first else ""
    return json.dumps({"answer": answer, "citation": selected}, ensure_ascii=False)


def reply(answer, model="actual-model"):
    response = Mock()
    response.json.return_value = {"answer": answer, "model": model}
    return response


def test_schema_requires_model_answer_and_one_model_selected_usable_reference(runtime, monkeypatch):
    module = runtime()
    answer = "Trip 17 visits Tokyo [E1]. Trip 18 visits Osaka [E3]."
    post = Mock(return_value=reply(envelope(answer)))
    monkeypatch.setattr(module.requests, "post", post)
    checks = Mock(wraps=module.deterministic_checks)
    monkeypatch.setattr(module, "deterministic_checks", checks)
    assert invoke(module) == {"model": "actual-model", "response": answer, "applied_feedback": None}
    assert post.call_count == 1
    payload = post.call_args.kwargs["json"]
    response_format = payload["response_format"]
    assert response_format["type"] == "json_schema" and response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]
    assert set(schema["required"]) == set(schema["properties"]) == {"answer", "citation"}
    assert schema["additionalProperties"] is False
    assert schema["properties"]["answer"]["type"] == "string"
    assert schema["properties"]["answer"]["maxLength"] == 800
    assert schema["properties"]["citation"]["enum"] == ["[E1]", "[E3]"]
    assert "pattern" not in json.dumps(response_format)
    assert payload["max_tokens"] == 450
    assert "Task: Recommend one trip" in payload["question"]
    assert "Trip 17 visits Tokyo." in payload["question"]
    checks.assert_called_once_with(answer, EVIDENCE)


@pytest.mark.parametrize("invalid", [
    "not json", '{"answer":"Tokyo', "null", "[]", "{}",
    '{"answer":"Tokyo"}', '{"citation":"[E1]"}',
    '{"answer":17,"citation":"[E1]"}', '{"answer":null,"citation":"[E1]"}',
    '{"answer":"Tokyo","citation":["E1"]}',
    '{"answer":"Tokyo","citation":"[E1]","extra":"x"}',
    envelope("", "[E1]"), envelope(" \n\t ", "[E1]"),
    envelope("[E1]", "[E1]"), envelope(" [E1] [E3] ", "[E1]"),
    envelope("Tokyo without a selected reference."),
    envelope("Tokyo", "[E99]"), envelope("Tokyo", "[E2]"),
    envelope("Tokyo", "[S1]"), envelope("Tokyo", "[e1]"), envelope("Tokyo", "[E1, E3]"),
    envelope("Tokyo [E1] and invented [E99]."),
    envelope("Tokyo [E1] and unavailable [E2]."),
    envelope("Tokyo [E1] and source ID [S1]."),
    envelope("Tokyo [E1] and combined reference [E1, E3]."),
    envelope("Tokyo [E1] and numeric reference [1]."),
    envelope("Tokyo [E1] and malformed reference [1, x]."),
    None, 17, [], {"answer": "Tokyo", "citation": "[E1]"},
])
def test_invalid_model_fields_or_mixed_references_need_one_real_repair(runtime, monkeypatch, invalid):
    module = runtime()
    corrected = "Trip 17 visits Tokyo [E1]."
    post = Mock(side_effect=[reply(invalid, "first-model"), reply(envelope(corrected), "repair-model")])
    monkeypatch.setattr(module.requests, "post", post)
    result = invoke(module)
    assert result == {"model": "repair-model", "response": corrected, "applied_feedback": None}
    assert post.call_count == 2
    first, second = [call.kwargs["json"] for call in post.call_args_list]
    assert second["response_format"] == first["response_format"]
    assert second["question"].startswith(first["question"])
    assert str(invalid) in second["question"]
    assert "Automatic citation validation (not human feedback)" in second["question"]
    assert "Permitted citations: [E1], [E3]." in second["question"]


@pytest.mark.parametrize("invalid", [
    "No citation.", "{}", envelope(""), envelope("Tokyo", "[E99]"),
    envelope("Tokyo", "[E2]"), envelope("Tokyo [E1] and [E99]."),
    envelope("Tokyo [E1] and malformed [1, x]."),
])
def test_persistently_invalid_output_fails_without_guessing_or_remapping_a_source(runtime, monkeypatch, invalid):
    module = runtime()
    post = Mock(return_value=reply(invalid))
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(module.AgentError, match="failed after one repair"):
        invoke(module)
    assert post.call_count == 2


@pytest.mark.parametrize("invalid", [None, 7, {}, []])
def test_nontext_repair_fails_without_a_third_generation(runtime, monkeypatch, invalid):
    module = runtime()
    post = Mock(side_effect=[reply("{}"), reply(invalid)])
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(module.AgentError, match="non-text Worker repair"):
        invoke(module)
    assert post.call_count == 2


def test_selected_reference_without_inline_reference_is_rendered_literally(runtime, monkeypatch):
    module = runtime()
    post = Mock(return_value=reply(envelope("Trip 18 visits Osaka.", "[E3]")))
    monkeypatch.setattr(module.requests, "post", post)
    assert invoke(module)["response"] == "Trip 18 visits Osaka. [E3]"
    assert post.call_count == 1


def test_existing_selected_reference_is_not_added_again_or_moved(runtime, monkeypatch):
    module = runtime()
    text = 'Trip "Tokyo" is recorded at C:\\travel\\nextstop [E1].\nKeep exact quotes and newline.'
    post = Mock(return_value=reply(envelope(text, "[E1]")))
    monkeypatch.setattr(module.requests, "post", post)
    assert invoke(module)["response"] == text
    assert post.call_count == 1


def test_other_inline_reference_does_not_replace_the_models_selected_reference(runtime, monkeypatch):
    module = runtime()
    answer = "Tokyo is recorded [E1]; Osaka is also recorded."
    post = Mock(return_value=reply(envelope(answer, "[E3]")))
    monkeypatch.setattr(module.requests, "post", post)
    assert invoke(module)["response"] == answer + " [E3]"
    assert post.call_count == 1


def test_primary_reference_does_not_hide_an_unknown_inline_reference(runtime, monkeypatch):
    module = runtime()
    post = Mock(return_value=reply(envelope("Tokyo [E99] is claimed.", "[E1]")))
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(module.AgentError, match="failed after one repair"):
        invoke(module)
    assert post.call_count == 2


def test_human_feedback_and_original_evidence_are_kept_during_model_repair(runtime, monkeypatch):
    module = runtime()
    post = Mock(side_effect=[reply("{}"), reply(envelope("Tokyo [E1]."))])
    monkeypatch.setattr(module.requests, "post", post)
    result = invoke(module, feedback="Include trip 17 and its recorded destination.", previous="An earlier answer [E1].")
    assert result["applied_feedback"] == "Include trip 17 and its recorded destination."
    for call in post.call_args_list:
        content = call.kwargs["json"]["question"]
        assert "Your previous response:\nAn earlier answer [E1]." in content
        assert "Human reviewer feedback to apply:\nInclude trip 17 and its recorded destination." in content
        assert "Trip 17 visits Tokyo." in content and "Task: Recommend one trip" in content


@pytest.mark.parametrize("model", [None, "", "a-different-real-model"])
def test_model_metadata_is_never_substituted(runtime, monkeypatch, model):
    module = runtime()
    monkeypatch.setattr(module.requests, "post", Mock(return_value=reply(envelope("Tokyo [E1]."), model)))
    assert invoke(module)["model"] == model


@pytest.mark.parametrize("citations, structured", [(False, False), (False, True), (True, False)])
def test_unconfigured_paths_keep_the_legacy_text_payload_and_450_tokens(runtime, monkeypatch, citations, structured):
    module = runtime(citations, structured)
    answer = "Original local answer." if not citations else "Tokyo [E1]."
    post = Mock(return_value=reply(answer, "legacy-model"))
    monkeypatch.setattr(module.requests, "post", post)
    assert invoke(module)["response"] == answer
    assert post.call_count == 1
    payload = post.call_args.kwargs["json"]
    assert set(payload) == {"system", "question", "max_tokens"}
    assert payload["max_tokens"] == 450
    if not citations:
        assert payload["system"] == module.load_prompt("worker_prompt.txt")
        assert post.call_args.kwargs["timeout"] == module.TIMEOUT


def test_local_path_keeps_the_legacy_fake_function_signature(runtime, monkeypatch):
    module = runtime(citations=False)
    calls = []
    def legacy(system, content, max_tokens=500):
        calls.append((system, content, max_tokens))
        return "Legacy output.", "local-model"
    monkeypatch.setattr(module, "ask_ai_mode", legacy)
    assert invoke(module)["response"] == "Legacy output."
    assert len(calls) == 1 and calls[0][2] == 450


def test_oversized_prose_is_repaired_instead_of_silently_truncated(runtime, monkeypatch):
    module = runtime()
    post = Mock(side_effect=[reply(envelope("x" * 801, "[E1]")), reply(envelope("Tokyo [E1]."))])
    monkeypatch.setattr(module.requests, "post", post)
    assert invoke(module)["response"] == "Tokyo [E1]."
    assert post.call_count == 2 and "x" * 801 in post.call_args_list[1].kwargs["json"]["question"]


@pytest.mark.parametrize("task, limit", [("Recommend one trip", 800), ("Output a table.", 2400)])
def test_oversized_answer_cannot_be_trimmed_into_a_passing_result(runtime, monkeypatch, task, limit):
    module = runtime()
    post = Mock(return_value=reply(envelope("x" * (limit + 1), "[E1]")))
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(module.AgentError, match="string length limit"):
        module.work(task, PLAN, EVIDENCE)
    assert post.call_count == 2


def test_exact_prose_boundary_is_preserved_without_a_model_repair(runtime, monkeypatch):
    module = runtime()
    answer = "x" * 795 + " [E1]"
    assert len(answer) == 800
    post = Mock(return_value=reply(envelope(answer)))
    monkeypatch.setattr(module.requests, "post", post)
    assert invoke(module)["response"] == answer and post.call_count == 1


def test_generation_and_repair_share_360_seconds(runtime, monkeypatch):
    module = runtime()
    now = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs)
        now[0] += 200 if len(calls) == 1 else 150
        return reply(envelope("No selected reference.") if len(calls) == 1 else envelope("Tokyo [E1]."))
    monkeypatch.setattr(module.requests, "post", post)
    assert invoke(module)["response"] == "Tokyo [E1]."
    assert [call["timeout"] for call in calls] == [360, 160]
    assert calls[0]["json"]["response_format"] == calls[1]["json"]["response_format"]


@pytest.mark.parametrize("elapsed", [(360,), (200, 161)])
def test_no_answer_is_returned_after_the_shared_deadline(runtime, monkeypatch, elapsed):
    module = runtime()
    now = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs["timeout"])
        now[0] += elapsed[len(calls) - 1]
        return reply(envelope("No citation.") if len(calls) == 1 else envelope("Tokyo [E1]."))
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(module.AgentError, match="generation deadline"):
        invoke(module)
    assert calls == ([360] if len(elapsed) == 1 else [360, 160])


@pytest.mark.parametrize("failure_at", [1, 2])
@pytest.mark.parametrize("error", [requests.Timeout("generation timed out"), requests.HTTPError("HTTP 503")])
def test_transport_failure_does_not_create_an_extra_retry(runtime, monkeypatch, failure_at, error):
    module = runtime()
    post = Mock(side_effect=[reply(envelope("No citation."))] * (failure_at - 1) + [error])
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(module.AgentError, match="generation failed"):
        invoke(module)
    assert post.call_count == failure_at


def test_unavailable_evidence_fails_before_any_model_generation(runtime, monkeypatch):
    module = runtime()
    evidence = copy.deepcopy(EVIDENCE)
    for item in evidence:
        item["ok"] = False
    post = Mock()
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(module.AgentError, match="No usable evidence"):
        module.work("Recommend a trip", PLAN, evidence)
    post.assert_not_called()


def test_ask_ai_mode_only_forwards_an_explicit_schema(runtime, monkeypatch):
    module = runtime()
    post = Mock(return_value=reply(envelope("Tokyo [E1].")))
    monkeypatch.setattr(module.requests, "post", post)
    module.ask_ai_mode("System", "Task", max_tokens=450, timeout=17)
    assert post.call_args.kwargs["json"] == {"system": "System", "question": "Task", "max_tokens": 450}
    assert post.call_args.kwargs["timeout"] == 17
    schema = module._worker_response_format(["E1"])
    module.ask_ai_mode("System", "Task", response_format=schema)
    assert post.call_args.kwargs["json"]["response_format"] == schema


def test_structured_error_preserves_the_real_upstream_failure_detail(runtime, monkeypatch):
    module = runtime()
    response = Mock()
    response.json.return_value = {"error": "AI recommendation request failed",
                                  "detail": "Structured completion was truncated at its output token limit."}
    response.raise_for_status.side_effect = requests.HTTPError("503 Service Unavailable", response=response)
    post = Mock(return_value=response)
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(module.AgentError) as caught:
        invoke(module)
    assert "truncated at its output token limit" in str(caught.value)
    assert "Start it with ./scripts/ai_services.sh up" not in str(caught.value)
    assert post.call_count == 1


TABLE_TASK = ("Output only this Markdown table, one row for each supplied trip.\n"
              "| Trip | Destination | Reason | Evidence |\n| --- | --- | --- | --- |\n"
              "An example reference [E99] illustrates syntax only.")
TABLE_ROWS = {"rows": [
    {"cells": ["17", "Tokyo", "Recorded destination."], "citation": "[E1]"},
    {"cells": ["18", "Osaka", "Recorded destination."], "citation": "[E3]"},
]}
RENDERED_TABLE = ("| Trip | Destination | Reason | Evidence |\n| --- | --- | --- | --- |\n"
                  "| 17 | Tokyo | Recorded destination. | [E1] |\n"
                  "| 18 | Osaka | Recorded destination. | [E3] |")


def test_explicit_header_uses_model_rows_and_each_rows_selected_reference(runtime, monkeypatch):
    module = runtime()
    post = Mock(return_value=reply(json.dumps(TABLE_ROWS)))
    monkeypatch.setattr(module.requests, "post", post)
    checks = Mock(wraps=module.deterministic_checks)
    monkeypatch.setattr(module, "deterministic_checks", checks)
    assert module.work(TABLE_TASK, PLAN, EVIDENCE)["response"] == RENDERED_TABLE
    payload = post.call_args.kwargs["json"]
    assert payload["max_tokens"] == 1200
    row = payload["response_format"]["json_schema"]["schema"]["properties"]["rows"]["items"]
    assert row["properties"]["cells"]["minItems"] == row["properties"]["cells"]["maxItems"] == 3
    assert row["properties"]["citation"]["enum"] == ["[E1]", "[E3]"]
    assert "ONLY permitted evidence citations are [E1], [E3]" in payload["system"]
    assert "Ignore citation examples naming an ID outside this permitted list" in payload["system"]
    assert TABLE_TASK in payload["question"]
    checks.assert_called_once_with(RENDERED_TABLE, EVIDENCE)


def test_wrong_row_reference_repairs_with_all_original_rows_and_human_feedback(runtime, monkeypatch):
    module = runtime()
    invalid = copy.deepcopy(TABLE_ROWS)
    invalid["rows"][1]["citation"] = "[E99]"
    post = Mock(side_effect=[reply(json.dumps(invalid)), reply(json.dumps(TABLE_ROWS), "repair-model")])
    monkeypatch.setattr(module.requests, "post", post)
    result = module.work(TABLE_TASK, PLAN, EVIDENCE, feedback="Retain both trip rows.", previous="Earlier table [E1].")
    assert result["response"] == RENDERED_TABLE and result["model"] == "repair-model"
    assert result["applied_feedback"] == "Retain both trip rows."
    first, repair = [call.kwargs["json"] for call in post.call_args_list]
    assert repair["question"].startswith(first["question"])
    assert json.dumps(invalid) in repair["question"]
    for payload in (first, repair):
        assert TABLE_TASK in payload["question"]
        assert "Human reviewer feedback to apply:\nRetain both trip rows." in payload["question"]
        assert "Your previous response:\nEarlier table [E1]." in payload["question"]
        assert "Trip 17 visits Tokyo." in payload["question"] and "Trip 18 visits Osaka." in payload["question"]
        assert payload["max_tokens"] == 1200


@pytest.mark.parametrize("citations, structured", [(False, False), (False, True), (True, False)])
def test_table_requests_do_not_change_legacy_local_payloads(runtime, monkeypatch, citations, structured):
    module = runtime(citations, structured)
    post = Mock(return_value=reply(RENDERED_TABLE))
    monkeypatch.setattr(module.requests, "post", post)
    assert module.work(TABLE_TASK, PLAN, EVIDENCE)["response"] == RENDERED_TABLE
    assert post.call_count == 1
    assert post.call_args.kwargs["json"]["max_tokens"] == 450
    assert "response_format" not in post.call_args.kwargs["json"]


def test_table_generation_and_model_repair_still_share_360_seconds(runtime, monkeypatch):
    module = runtime()
    now = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs)
        now[0] += 200 if len(calls) == 1 else 150
        return reply("{}" if len(calls) == 1 else json.dumps(TABLE_ROWS))
    monkeypatch.setattr(module.requests, "post", post)
    assert module.work(TABLE_TASK, PLAN, EVIDENCE)["response"] == RENDERED_TABLE
    assert [call["timeout"] for call in calls] == [360, 160]
    assert all(call["json"]["max_tokens"] == 1200 for call in calls)


def test_structured_system_uses_actual_ids_instead_of_the_tasks_unavailable_example(runtime, monkeypatch):
    module = runtime()
    task = "Recommend one trip and cite evidence, for example [E2]."
    post = Mock(return_value=reply(envelope("Tokyo [E1].")))
    monkeypatch.setattr(module.requests, "post", post)
    assert module.work(task, PLAN, EVIDENCE)["response"] == "Tokyo [E1]."
    payload = post.call_args.kwargs["json"]
    assert "Task: " + task in payload["question"]
    assert "ONLY permitted evidence citations are [E1], [E3]" in payload["system"]
    assert "Ignore citation examples naming an ID outside this permitted list" in payload["system"]
    assert payload["response_format"]["json_schema"]["schema"]["properties"]["citation"]["enum"] == ["[E1]", "[E3]"]


def test_header_without_the_word_table_still_selects_rows_mode_and_1200_tokens(runtime, monkeypatch):
    module = runtime()
    task = ("Return exactly these columns, one row per supplied record.\n"
            "| Trip | Destination | Reason | Evidence |\n| --- | --- | --- | --- |")
    assert re.search(r"\btable\b", task, re.IGNORECASE) is None
    post = Mock(return_value=reply(json.dumps(TABLE_ROWS)))
    monkeypatch.setattr(module.requests, "post", post)
    assert module.work(task, PLAN, EVIDENCE)["response"] == RENDERED_TABLE
    payload = post.call_args.kwargs["json"]
    assert payload["max_tokens"] == 1200
    assert set(payload["response_format"]["json_schema"]["schema"]["properties"]) == {"rows"}
