"""Unit tests for services/mcp_client.py and services/rag_client.py.

    python -m pytest student-3/tests/test_clients.py
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from services import mcp_client, rag_client  # noqa: E402


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_mcp_sends_a_json_rpc_tools_call(monkeypatch):
    sent = {}

    def fake_post(url, json=None, timeout=None):
        sent.update(url=url, payload=json, timeout=timeout)
        return FakeResponse({"jsonrpc": "2.0", "id": json["id"], "result": {"isError": False}})

    monkeypatch.setattr(requests, "post", fake_post)
    result = mcp_client.call_tool("find_travel_mates", {"status": "open"})

    assert sent["url"].endswith("/mcp")
    assert sent["payload"]["jsonrpc"] == "2.0"
    assert sent["payload"]["method"] == "tools/call"
    assert sent["payload"]["params"] == {"name": "find_travel_mates", "arguments": {"status": "open"}}
    assert result == {"isError": False}


def test_mcp_request_ids_increase(monkeypatch):
    ids = []

    def fake_post(url, json=None, timeout=None):
        ids.append(json["id"])
        return FakeResponse({"result": {}})

    monkeypatch.setattr(requests, "post", fake_post)
    mcp_client.call_tool("find_travel_mates", {})
    mcp_client.call_tool("find_travel_mates", {})
    assert ids[1] == ids[0] + 1


def test_mcp_protocol_error_raises_value_error(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(
        {"error": {"code": -32601, "message": "unknown method"}}))
    with pytest.raises(ValueError, match="unknown method"):
        mcp_client.call_tool("find_travel_mates", {})


def test_mcp_boundary_refusal_is_returned_not_raised(monkeypatch):
    refusal = {"isError": True, "boundary": "schema-checked"}
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"result": refusal}))
    assert mcp_client.call_tool("find_travel_mates", {"sql": "x"})["boundary"] == "schema-checked"


def test_mcp_http_error_propagates(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({}, 500))
    with pytest.raises(requests.HTTPError):
        mcp_client.call_tool("find_travel_mates", {})


def test_rag_posts_the_question_with_a_long_timeout(monkeypatch):
    sent = {}

    def fake_post(url, json=None, timeout=None):
        sent.update(url=url, payload=json, timeout=timeout)
        return FakeResponse({"grounded": True})

    monkeypatch.setattr(requests, "post", fake_post)
    assert rag_client.ask("own post?") == {"grounded": True}
    assert sent["url"].endswith("/ask")
    assert sent["payload"] == {"question": "own post?"}
    assert sent["timeout"] >= 180


def test_health_helpers_return_the_server_json(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse({"status": "running"}))
    assert mcp_client.health() == {"status": "running"}
    assert rag_client.health() == {"status": "running"}