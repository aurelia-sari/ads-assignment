"""Unit tests for the student-4 MCP and RAG proxy endpoints.

No network and no running services. The shared servers are replaced with
stubs, so these run in CI where MCP_ENABLED and RAG_ENABLED are false.

    python -m pytest student-4/tests/test_ai_tools.py
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app import app  # noqa: E402
from services import mcp_client, rag_client  # noqa: E402

HTMX = {"HX-Request": "true"}


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a disabled integration must not make a network call")

    monkeypatch.setattr(requests, "get", refuse)
    monkeypatch.setattr(requests, "post", refuse)


@pytest.fixture
def disabled(monkeypatch, no_network):
    monkeypatch.setattr(mcp_client, "MCP_ENABLED", False)
    monkeypatch.setattr(rag_client, "RAG_ENABLED", False)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(mcp_client, "MCP_ENABLED", True)
    monkeypatch.setattr(rag_client, "RAG_ENABLED", True)


def stub_post(monkeypatch, response):
    def fake_post(url, **kwargs):
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(requests, "post", fake_post)


# Disabled path, as in CI

def test_status_reports_both_disabled(client, disabled):
    response = client.get("/ai-tools/status")
    assert response.status_code == 200
    assert response.get_json() == {"mcp": "disabled", "rag": "disabled"}


def test_mcp_disabled_returns_clear_response(client, disabled):
    response = client.post("/mcp/destination-guide", json={"query": "Sydney"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "disabled"
    assert "MCP_ENABLED=false" in body["detail"]


def test_rag_disabled_returns_clear_response(client, disabled):
    response = client.post("/rag/ask", json={"question": "What does a travel guide cover?"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "disabled"
    assert "RAG_ENABLED=false" in body["detail"]


def test_disabled_htmx_fragment_is_swappable(client, disabled):
    response = client.post("/mcp/destination-guide", data={"query": "Sydney"}, headers=HTMX)
    assert response.status_code == 200
    assert "MCP is disabled" in response.get_data(as_text=True)

    response = client.post("/rag/ask", data={"question": "hi"}, headers=HTMX)
    assert response.status_code == 200
    assert "RAG is disabled" in response.get_data(as_text=True)


def test_empty_question_is_rejected_before_any_call(client, disabled):
    response = client.post("/rag/ask", json={"question": "  "})
    assert response.status_code == 400


def test_oversized_question_is_rejected(client, disabled):
    response = client.post("/rag/ask", json={"question": "x" * 501})
    assert response.status_code == 400


# Unavailable path

def test_mcp_unreachable_degrades_gracefully(client, enabled, monkeypatch):
    stub_post(monkeypatch, requests.ConnectionError("refused"))

    response = client.post("/mcp/destination-guide", json={"query": "Sydney"})
    assert response.status_code == 503
    assert response.get_json()["status"] == "unavailable"

    response = client.post("/mcp/destination-guide", data={"query": "Sydney"}, headers=HTMX)
    assert response.status_code == 200
    assert "could not be reached" in response.get_data(as_text=True)


def test_rag_generation_failure_passes_on_the_hint(client, enabled, monkeypatch):
    stub_post(monkeypatch, FakeResponse({"error": "RAG generation failed", "hint": "Is AI-Mode running?"}, 503))

    response = client.post("/rag/ask", json={"question": "Is guide weather a forecast?"})
    assert response.status_code == 503
    assert response.get_json()["detail"] == "Is AI-Mode running?"


def test_status_reports_unavailable(client, enabled, monkeypatch):
    def refuse(*args, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(requests, "get", refuse)
    assert client.get("/ai-tools/status").get_json() == {"mcp": "unavailable", "rag": "unavailable"}


# Enabled path with stubbed servers

def test_mcp_structured_result_is_rendered(client, enabled, monkeypatch):
    result = {
        "isError": False,
        "structuredContent": {
            "tool": "lookup_destination_guide",
            "source": "student-4-db",
            "arguments": {"query": "Sydney"},
            "rows": [{"id": 1, "city": "Sydney", "region": "New South Wales", "country": "Australia"}],
            "row_count": 1,
            "truncated": False,
        },
    }
    stub_post(monkeypatch, FakeResponse({"jsonrpc": "2.0", "id": 1, "result": result}))

    response = client.post("/mcp/destination-guide", data={"query": "Sydney"}, headers=HTMX)
    html = response.get_data(as_text=True)
    assert "returned 1 row(s)" in html
    assert "/api/student-4/guides/1" in html


def test_mcp_boundary_refusal_names_the_boundary(client, enabled, monkeypatch):
    result = {
        "isError": True,
        "boundary": "schema-checked",
        "content": [{"type": "text", "text": "missing required argument: query"}],
    }
    stub_post(monkeypatch, FakeResponse({"jsonrpc": "2.0", "id": 1, "result": result}))

    response = client.post("/mcp/destination-guide", data={"query": ""}, headers=HTMX)
    html = response.get_data(as_text=True)
    assert "schema-checked" in html
    assert "Nothing was read from the database" in html


def test_rag_grounded_answer_shows_citations_and_confidence(client, enabled, monkeypatch):
    stub_post(monkeypatch, FakeResponse({
        "grounded": True,
        "answer": "No, it describes typical seasonal conditions [1].",
        "confidence": "high",
        "confidence_reason": "best score 14",
        "citations": [{"number": 1, "source": "travel/accounts-and-guides.md",
                       "section": "Travel guides", "score": 14.0}],
    }))

    response = client.post("/rag/ask", data={"question": "Is guide weather a forecast?"}, headers=HTMX)
    html = response.get_data(as_text=True)
    assert "confidence: high" in html
    assert "travel/accounts-and-guides.md" in html


def test_rag_insufficient_context_has_no_sources(client, enabled, monkeypatch):
    stub_post(monkeypatch, FakeResponse({
        "grounded": False,
        "answer": "I don't have enough information.",
        "confidence": "insufficient",
        "confidence_reason": "no chunk scored above zero",
        "citations": [],
    }))

    response = client.post("/rag/ask", data={"question": "What is the capital of Peru?"}, headers=HTMX)
    html = response.get_data(as_text=True)
    assert "insufficient context" in html
    assert "Sources" not in html
