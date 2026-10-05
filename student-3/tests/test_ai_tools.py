#for MCP + RAG routes

"""Unit tests for the student-3 MCP and RAG routes.

No network and no running services: the shared servers are stubbed, so these
run anywhere, including CI where MCP_ENABLED and RAG_ENABLED are false.

    python -m pytest student-3/tests/test_ai_tools.py
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

import app as travel_app  # noqa: E402
from services import mcp_client, rag_client  # noqa: E402


@pytest.fixture
def client():
    travel_app.app.config["TESTING"] = True
    return travel_app.app.test_client()


@pytest.fixture
def disabled(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a disabled integration must not call the shared server")

    monkeypatch.setattr(travel_app, "MCP_ENABLED", False)
    monkeypatch.setattr(travel_app, "RAG_ENABLED", False)
    monkeypatch.setattr(mcp_client, "call_tool", refuse)
    monkeypatch.setattr(rag_client, "ask", refuse)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(travel_app, "MCP_ENABLED", True)
    monkeypatch.setattr(travel_app, "RAG_ENABLED", True)


# Disabled path, as in CI

def test_mcp_disabled_returns_503_without_calling_the_server(client, disabled):
    response = client.post("/mcp/find-mates", data={"destination": "Bali"})
    assert response.status_code == 503
    assert "disabled in this environment" in response.get_data(as_text=True)


def test_rag_disabled_returns_503_without_calling_the_server(client, disabled):
    response = client.post("/ai/ask-grounded", data={"question": "hello"})
    assert response.status_code == 503
    assert "disabled in this environment" in response.get_data(as_text=True)


def test_status_reports_both_disabled(client, disabled):
    body = client.get("/ai/status").get_json()
    assert body["mcp"] == "disabled" and body["rag"] == "disabled"
    assert body["mcp_enabled"] is False and body["rag_enabled"] is False


# MCP, enabled

def test_mcp_defaults_status_to_open(client, enabled, monkeypatch):
    seen = {}

    def fake_call(name, arguments):
        seen["name"], seen["arguments"] = name, arguments
        return {"isError": False, "content": [{"type": "text", "text": "ok"}],
                "structuredContent": {"rows": []}}

    monkeypatch.setattr(mcp_client, "call_tool", fake_call)
    client.post("/mcp/find-mates", data={"destination": "Bali"})
    assert seen["name"] == "find_travel_mates"
    assert seen["arguments"] == {"destination": "Bali", "status": "open"}


def test_mcp_empty_destination_sends_only_status(client, enabled, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mcp_client, "call_tool",
        lambda name, arguments: seen.update(arguments=arguments) or
        {"isError": False, "content": [{"text": "ok"}], "structuredContent": {"rows": []}},
    )
    client.post("/mcp/find-mates", data={"destination": ""})
    assert seen["arguments"] == {"status": "open"}


def test_mcp_result_rows_are_rendered(client, enabled, monkeypatch):
    result = {
        "isError": False,
        "content": [{"type": "text", "text": "find_travel_mates returned 1 row(s) from student-3-db"}],
        "structuredContent": {"rows": [{
            "destination": "Bali, Indonesia", "start_date": "2026-10-12",
            "end_date": "2026-10-19", "travel_style": "into hiking"}]},
    }
    monkeypatch.setattr(mcp_client, "call_tool", lambda n, a: result)
    html = client.post("/mcp/find-mates", data={}).get_data(as_text=True)
    assert "returned 1 row(s)" in html
    assert "Bali, Indonesia" in html


def test_mcp_boundary_refusal_names_the_boundary(client, enabled, monkeypatch):
    refusal = {"isError": True, "boundary": "schema-checked",
               "content": [{"type": "text", "text": "argument 'destination' exceeds 60 characters"}]}
    monkeypatch.setattr(mcp_client, "call_tool", lambda n, a: refusal)
    html = client.post("/mcp/find-mates", data={"destination": "x" * 61}).get_data(as_text=True)
    assert "Tool call refused" in html and "Boundary: schema-checked" in html


def test_mcp_transport_failure_returns_502(client, enabled, monkeypatch):
    def boom(name, arguments):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(mcp_client, "call_tool", boom)
    response = client.post("/mcp/find-mates", data={})
    assert response.status_code == 502
    assert "MCP request failed" in response.get_data(as_text=True)


# RAG, enabled

def test_rag_empty_question_is_rejected(client, enabled):
    response = client.post("/ai/ask-grounded", data={"question": "   "})
    assert response.status_code == 400


def test_rag_grounded_answer_shows_confidence_and_citations(client, enabled, monkeypatch):
    monkeypatch.setattr(rag_client, "ask", lambda q: {
        "grounded": True,
        "answer": "No, a traveller cannot connect to their own post [1].",
        "confidence": "high",
        "citations": [{"number": 1, "source": "travel/travel-mate-matching.md",
                       "section": "Connect requests", "excerpt": "Only the owner can accept."}],
    })
    html = client.post("/ai/ask-grounded", data={"question": "own post?"}).get_data(as_text=True)
    assert "Grounded answer" in html
    assert "pill-high" in html
    assert "travel/travel-mate-matching.md" in html


def test_rag_insufficient_context_has_no_citations(client, enabled, monkeypatch):
    monkeypatch.setattr(rag_client, "ask", lambda q: {
        "grounded": False, "answer": "I don't have enough information.",
        "confidence": "insufficient", "citations": []})
    html = client.post("/ai/ask-grounded", data={"question": "capital of Peru?"}).get_data(as_text=True)
    assert "Not enough context" in html
    assert "pill-insufficient" in html
    assert "compat-reason" not in html


def test_rag_transport_failure_returns_502(client, enabled, monkeypatch):
    def boom(question):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(rag_client, "ask", boom)
    response = client.post("/ai/ask-grounded", data={"question": "hello"})
    assert response.status_code == 502
    assert "RAG request failed" in response.get_data(as_text=True)