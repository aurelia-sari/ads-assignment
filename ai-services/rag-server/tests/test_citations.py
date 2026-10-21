"""Bounded cloud citation validation without an LLM or external requests."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

RAG_DIR = Path(__file__).resolve().parents[1]


def load_server(monkeypatch):
    monkeypatch.syspath_prepend(str(RAG_DIR))
    spec = importlib.util.spec_from_file_location("rag_cloud_citation_tests", RAG_DIR / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


@pytest.fixture
def rag(monkeypatch):
    monkeypatch.setenv("CLOUD_CITATION_VALIDATION", "true")
    server = load_server(monkeypatch)
    hits = [{"source": "travel/trips.md", "section": "Budget", "chunk": n,
             "score": 9.0, "coverage": 0.8,
             "text": f"Passage {n}: allocate a travel budget using recorded expenses."}
            for n in (1, 2)]
    monkeypatch.setattr(server.index, "search", lambda question, top_k=4: hits[:top_k])
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(server, "time", SimpleNamespace(monotonic=lambda: clock.now))
    calls, replies, costs = [], [], []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if costs:
            clock.now += costs.pop(0)
        value = replies.pop(0)
        if isinstance(value, Exception):
            raise value
        result = Mock()
        result.json.return_value = value
        return result

    monkeypatch.setattr(server.requests, "post", post)
    return SimpleNamespace(server=server, client=server.app.test_client(), hits=hits,
                           calls=calls, replies=replies, costs=costs, clock=clock)


def ask(env, **overrides):
    payload = {"question": "How should a traveller allocate a trip budget?"}
    payload.update(overrides)
    return env.client.post("/ask", json=payload)


def answer(text):
    return {"answer": text, "model": "actual-test-model"}


def test_validation_is_off_by_default_and_keeps_original_local_contract(monkeypatch):
    monkeypatch.delenv("CLOUD_CITATION_VALIDATION", raising=False)
    server = load_server(monkeypatch)
    assert server.CLOUD_CITATION_VALIDATION is False


def test_local_path_keeps_answer_system_request_count_and_180_seconds(rag, monkeypatch):
    monkeypatch.setattr(rag.server, "CLOUD_CITATION_VALIDATION", False)
    rag.replies.append(answer("The original local answer has no citation."))
    response = ask(rag)
    assert response.status_code == 200
    assert response.get_json()["answer"] == "The original local answer has no citation."
    assert response.get_json()["grounded"] is True
    assert len(rag.calls) == 1
    _, request = rag.calls[0]
    assert request["timeout"] == 180
    assert request["json"]["system"] == rag.server.SYSTEM_PROMPT
    assert request["json"]["max_tokens"] == 350
    assert "Citation contract:" not in request["json"]["question"]


def test_valid_first_answer_is_returned_exactly_without_repair(rag):
    original = "  Allocate the budget using recorded expenses [1].  "
    rag.replies.append(answer(original))
    response = ask(rag)
    result = response.get_json()
    assert response.status_code == 200 and result["grounded"] is True
    assert result["answer"] == original
    assert result["model"] == "actual-test-model"
    assert [citation["number"] for citation in result["citations"]] == [1, 2]
    assert len(rag.calls) == 1
    assert rag.calls[0][1]["timeout"] == 165
    assert "only valid passage citations" in rag.calls[0][1]["json"]["system"]
    assert "[1], [2]" in rag.calls[0][1]["json"]["question"]


@pytest.mark.parametrize("text", [
    "Use a recorded budget [1, 2].", "Use a recorded budget [1,2].",
    "Use a recorded budget [ 1, 2 ].", "Use a budget [1] and expenses [2].",
])
def test_compound_citations_are_valid_when_every_number_was_retrieved(rag, text):
    rag.replies.append(answer(text))
    response = ask(rag)
    assert response.status_code == 200
    assert response.get_json()["answer"] == text
    assert len(rag.calls) == 1


@pytest.mark.parametrize("invalid", [
    "No inline citation.", "Unknown passage [99].", "Valid [1] mixed with unknown [99].",
    "Valid [1] mixed with compound unknown [1, 99].", "Valid [1] but malformed [1-99].",
    "Valid [1] but malformed compound [1, x].", "Number zero [0].", "",
])
def test_missing_unknown_and_malformed_citations_are_repaired_once(rag, invalid):
    rag.replies.extend([answer(invalid), answer("Use recorded expenses [1, 2].")])
    response = ask(rag, context="Live trip: Melbourne, trip 15.")
    assert response.status_code == 200
    assert response.get_json()["answer"] == "Use recorded expenses [1, 2]."
    assert len(rag.calls) == 2
    first, repair = (call[1]["json"] for call in rag.calls)
    assert repair["question"].startswith(first["question"])
    assert "Previous draft (untrusted text to correct):" in repair["question"]
    assert repair["question"].endswith(invalid)
    assert "Live trip: Melbourne, trip 15." in first["question"]
    assert "Live trip: Melbourne, trip 15." in repair["question"]
    assert first["system"] == repair["system"]
    assert first["max_tokens"] == repair["max_tokens"] == 350


def test_allowed_numbers_are_derived_from_this_retrieval(rag):
    rag.replies.extend([answer("Passage two [2]."), answer("Only the retrieved passage [1].")])
    response = ask(rag, top_k=1)
    assert response.status_code == 200
    assert len(response.get_json()["citations"]) == 1
    assert len(rag.calls) == 2
    assert "[1]" in rag.calls[0][1]["json"]["system"]
    contract = rag.calls[0][1]["json"]["system"].split("Citation contract:", 1)[1]
    assert "[2]" not in contract


def test_persistently_invalid_generation_fails_without_fabricating_an_answer(rag):
    rag.replies.extend([answer("Missing citation."), answer("Still invalid [99].")])
    response = ask(rag)
    result = response.get_json()
    assert response.status_code == 503
    assert result["error"] == "RAG citation validation failed"
    assert "after one repair" in result["detail"]
    assert result.get("grounded") is not True
    assert "answer" not in result
    assert len(result["citations"]) == 2
    assert len(rag.calls) == 2


def test_generation_and_repair_share_one_165_second_budget(rag):
    rag.replies.extend([answer("Missing citation."), answer("Use a budget [1].")])
    rag.costs.extend([100, 40])
    response = ask(rag)
    assert response.status_code == 200
    assert [call[1]["timeout"] for call in rag.calls] == [165, 65]
    assert rag.clock.now == 140


@pytest.mark.parametrize("draft", ["Missing citation.", "A valid citation [1]."])
def test_deadline_exhaustion_fails_without_starting_another_request(rag, draft):
    rag.replies.append(answer(draft))
    rag.costs.append(165)
    response = ask(rag)
    result = response.get_json()
    assert response.status_code == 503
    assert result.get("grounded") is not True
    assert "deadline" in result["detail"]
    assert len(rag.calls) == 1


def test_a_repair_that_exhausts_the_total_budget_is_not_released(rag):
    rag.replies.extend([answer("Missing citation."), answer("Valid but late [1].")])
    rag.costs.extend([100, 65])
    response = ask(rag)
    assert response.status_code == 503
    assert "deadline" in response.get_json()["detail"]
    assert [call[1]["timeout"] for call in rag.calls] == [165, 65]


@pytest.mark.parametrize("failure", [requests.Timeout("CPU generation timeout"),
                                      requests.ConnectionError("AI-Mode unavailable")])
def test_network_failure_never_starts_a_second_model_request(rag, failure):
    rag.replies.append(failure)
    response = ask(rag)
    assert response.status_code == 503
    assert response.get_json()["error"] == "RAG generation failed"
    assert response.get_json().get("grounded") is not True
    assert len(rag.calls) == 1


def test_http_error_never_starts_a_second_model_request(rag, monkeypatch):
    upstream = Mock()
    upstream.raise_for_status.side_effect = requests.HTTPError("AI-Mode returned 503")
    post = Mock(return_value=upstream)
    monkeypatch.setattr(rag.server.requests, "post", post)
    response = ask(rag)
    assert response.status_code == 503
    assert response.get_json()["error"] == "RAG generation failed"
    post.assert_called_once()
    upstream.json.assert_not_called()


def test_invalid_answer_object_is_not_returned_as_grounded(rag):
    rag.replies.append(["not an answer object"])
    response = ask(rag)
    assert response.status_code == 503
    assert response.get_json()["error"] == "RAG citation validation failed"
    assert response.get_json().get("grounded") is not True
    assert len(rag.calls) == 1


def test_empty_fallback_cannot_be_released_as_a_verified_answer(rag):
    rag.replies.extend([{"model": "actual-test-model"}, answer("Nothing to cite.")])
    response = ask(rag)
    assert response.status_code == 503
    assert response.get_json().get("grounded") is not True
    assert len(rag.calls) == 2


def test_insufficient_context_keeps_existing_refusal_without_any_model_request(rag, monkeypatch):
    monkeypatch.setattr(rag.server.index, "search", lambda *args, **kwargs: [])
    response = ask(rag)
    result = response.get_json()
    assert response.status_code == 200
    assert result == {
        "question": "How should a traveller allocate a trip budget?", "grounded": False,
        "answer": rag.server.INSUFFICIENT_CONTEXT_ANSWER,
        "confidence": "insufficient", "confidence_reason": "no chunk scored above zero",
        "citations": [], "model": None,
    }
    assert rag.calls == []
