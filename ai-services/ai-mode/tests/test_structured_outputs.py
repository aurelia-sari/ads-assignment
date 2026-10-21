"""Opt-in structured generation keeps the existing shared AI transport intact."""

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


SERVICE = Path(__file__).resolve().parents[1]
FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "grounded_worker",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"answer": {"type": "string", "pattern": r".*\[E1\].*"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
    },
}


@pytest.fixture(scope="module")
def runtime():
    spec = importlib.util.spec_from_file_location("structured_output_ai_mode", SERVICE / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    module.client.close()


def completion(content='{"answer":"Tokyo [E1]."}', finish_reason="stop", refusal=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        finish_reason=finish_reason,
        message=SimpleNamespace(content=content, refusal=refusal),
    )])


@pytest.fixture
def sdk(runtime, monkeypatch):
    create = Mock(return_value=completion())
    monkeypatch.setattr(runtime.client.chat.completions, "create", create)
    return create


def recommend(runtime, **payload):
    return runtime.app.test_client().post("/recommend", json={
        "question": "Recommend Tokyo with its evidence.",
        "system": "Answer only from the evidence.",
        **payload,
    })


def test_legacy_completion_preserves_sdk_arguments_and_text_behavior(runtime, sdk):
    sdk.return_value = completion("  Original answer.  ", finish_reason="length")
    messages = [{"role": "user", "content": "Original local request."}]
    assert runtime.create_chat_completion(messages) == "Original answer."
    sdk.assert_called_once_with(model=runtime.OLLAMA_MODEL, messages=messages,
                                max_tokens=300, temperature=0.2)


def test_legacy_completion_keeps_explicit_model_and_temperature(runtime, sdk):
    runtime.create_chat_completion([], max_tokens=80, temperature=0.7, model="selected-local-model")
    sdk.assert_called_once_with(model="selected-local-model", messages=[],
                                max_tokens=80, temperature=0.7)


def test_legacy_recommend_keeps_the_existing_function_signature_and_wrappers(runtime, monkeypatch):
    calls = []

    def legacy_generate(messages, max_tokens=300):
        calls.append((messages, max_tokens))
        return "Original model response."

    monkeypatch.setattr(runtime, "create_chat_completion", legacy_generate)
    response = recommend(runtime, context="Trip 17 visits Tokyo.", max_tokens=81)
    assert response.status_code == 200
    assert response.get_json() == {"answer": "Original model response.", "model": runtime.OLLAMA_MODEL}
    assert calls == [([
        {"role": "system", "content": "Answer only from the evidence."},
        {"role": "user", "content": "Live application data:\nTrip 17 visits Tokyo.\n\n"
         "Traveller question:\nRecommend Tokyo with its evidence."},
    ], 81)]


def test_structured_recommend_passes_the_complete_schema_and_uses_zero_temperature(runtime, sdk):
    response = recommend(runtime, response_format=FORMAT, max_tokens=450,
                         context="[E1] Tokyo is the recorded destination.", model="not-selected")
    assert response.status_code == 200
    assert response.get_json() == {"answer": '{"answer":"Tokyo [E1]."}', "model": runtime.OLLAMA_MODEL}
    options = sdk.call_args.kwargs
    assert options["response_format"] == FORMAT
    assert options["temperature"] == 0
    assert options["max_tokens"] == 450
    assert options["model"] == runtime.OLLAMA_MODEL
    assert options["messages"][0]["content"] == "Answer only from the evidence."
    assert "[E1] Tokyo is the recorded destination." in options["messages"][1]["content"]
    assert sdk.call_count == 1


def test_structured_generation_does_not_modify_model_authored_answer_content(runtime, sdk):
    raw = '{"answer":"| Place | Evidence |\\n| Tokyo | [E1] |"}'
    sdk.return_value = completion(" \n" + raw + "\n ")
    assert recommend(runtime, response_format=FORMAT).get_json()["answer"] == raw


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls", None])
def test_incomplete_structured_completion_fails_without_returning_partial_answer(runtime, sdk, reason):
    sdk.return_value = completion('{"answer":"Tokyo [E1]', finish_reason=reason)
    response = recommend(runtime, response_format=FORMAT)
    assert response.status_code == 503
    body = response.get_json()
    assert "answer" not in body
    assert "Structured generation did not complete" in body["detail"]
    assert f"finish_reason={reason}" in body["detail"]
    assert sdk.call_count == 1


@pytest.mark.parametrize("content", [None, "", " \n\t "])
def test_empty_structured_completion_fails_without_fabricating_an_answer(runtime, sdk, content):
    sdk.return_value = completion(content)
    response = recommend(runtime, response_format=FORMAT)
    assert response.status_code == 503
    assert "answer" not in response.get_json()
    assert "returned no text" in response.get_json()["detail"]
    assert sdk.call_count == 1


def test_structured_refusal_is_not_returned_as_a_grounded_answer(runtime, sdk):
    sdk.return_value = completion("An answer-looking refusal.", refusal="Cannot complete this request.")
    response = recommend(runtime, response_format=FORMAT)
    assert response.status_code == 503
    assert "answer" not in response.get_json()
    assert "refused by the model" in response.get_json()["detail"]


def test_missing_structured_completion_has_a_clear_error(runtime, sdk):
    sdk.return_value = SimpleNamespace(choices=[])
    response = recommend(runtime, response_format=FORMAT)
    assert response.status_code == 503
    assert "returned no completion" in response.get_json()["detail"]
    assert "answer" not in response.get_json()


def test_structured_backend_error_is_not_retried_or_replaced_with_free_text(runtime, sdk):
    sdk.side_effect = RuntimeError("Backend cannot enforce this schema.")
    response = recommend(runtime, response_format=FORMAT)
    assert response.status_code == 503
    assert response.get_json()["detail"] == "Backend cannot enforce this schema."
    assert "answer" not in response.get_json()
    assert sdk.call_count == 1


@pytest.mark.parametrize("invalid", [
    None, "json_schema", [], {}, {"type": "json_object"},
    {"type": "json_schema"}, {"type": "json_schema", "json_schema": []},
    {"type": "json_schema", "json_schema": {"schema": {"type": "object"}}},
    {"type": "json_schema", "json_schema": {"name": "bad name", "schema": {"type": "object"}}},
    {"type": "json_schema", "json_schema": {"name": "x" * 65, "schema": {"type": "object"}}},
    {"type": "json_schema", "json_schema": {"name": "worker", "schema": {}}},
    {"type": "json_schema", "json_schema": {"name": "worker", "schema": []}},
    {"type": "json_schema", "json_schema": {"name": "worker", "schema": None}},
    {"type": "json_schema", "json_schema": {"name": "worker", "schema": {"type": "object"}, "strict": "true"}},
])
def test_malformed_response_format_is_rejected_before_model_generation(runtime, sdk, invalid):
    response = recommend(runtime, response_format=invalid)
    assert response.status_code == 400
    assert "response_format" in response.get_json()["error"]
    sdk.assert_not_called()


def test_schema_envelope_accepts_optional_strict_without_changing_it(runtime, sdk):
    response_format = copy.deepcopy(FORMAT)
    response_format["json_schema"].pop("strict")
    response_format["json_schema"]["name"] = "Worker_1-v2"
    response = recommend(runtime, response_format=response_format)
    assert response.status_code == 200
    assert sdk.call_args.kwargs["response_format"] == response_format


def test_chat_ignores_the_new_recommend_only_option_and_keeps_legacy_sdk_contract(runtime, sdk):
    sdk.return_value = completion("Local chat answer.", finish_reason="length")
    response = runtime.app.test_client().post("/chat", json={
        "question": "One tip?", "system": "Original chat system.",
        "response_format": FORMAT, "max_tokens": 90,
    })
    assert response.status_code == 200
    assert response.get_json() == {"answer": "Local chat answer.", "model": runtime.OLLAMA_MODEL}
    assert "response_format" not in sdk.call_args.kwargs
    assert sdk.call_args.kwargs["temperature"] == 0.2
    assert sdk.call_args.kwargs["max_tokens"] == 90


def test_model_readiness_retains_original_unstructured_call(runtime, sdk):
    sdk.return_value = completion("ready")
    response = runtime.app.test_client().get("/model")
    assert response.status_code == 200
    assert response.get_json() == {"model": runtime.OLLAMA_MODEL, "reachable": True}
    assert "response_format" not in sdk.call_args.kwargs
    assert sdk.call_args.kwargs["temperature"] == 0.2
    assert sdk.call_args.kwargs["max_tokens"] == 5
