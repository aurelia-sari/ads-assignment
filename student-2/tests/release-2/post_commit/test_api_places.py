"""Real HTTP tests against student-2's backend, like Lab 11's API tests."""
import os
import requests
import pytest

API = os.getenv("STUDENT2_API_URL", "http://localhost:5102").rstrip("/")


def test_service_health():
    response = requests.get(f"{API}/health", timeout=5)
    assert response.status_code == 200
    assert response.json()["service"] == "student-2-api"


def test_places_exist():
    response = requests.get(f"{API}/places", timeout=10)
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]
    assert "Sydney Opera House" in response.text


def test_missing_place_fields_rejected():
    response = requests.post(f"{API}/places", data={}, timeout=10)
    assert response.status_code == 400


@pytest.mark.parametrize("path,payload", [
    ("ai/recommend", {"question": "Sydney"}),
    ("mcp/search-places", {"category": "attraction"}),
    ("rag/search", {"query": "Sydney"}),
    ("rag/ask", {"question": "Sydney"}),
    ("rag/reindex", {}),
    ("agents/workflows", {"task": "Sydney attractions", "city": "Sydney"}),
])
def test_cloud_integrations_disabled(path, payload):
    # This deployment suite requires all four feature flags to be false.
    response = requests.post(f"{API}/{path}", json=payload, timeout=5)
    assert response.status_code == 503
    assert "disabled" in response.json()["error"].lower()


def test_unknown_place_returns_404():
    response = requests.get(f"{API}/places/edit", params={"id": 2147483647}, timeout=10)
    assert response.status_code == 404


def test_favourites_require_user_id():
    assert requests.get(f"{API}/favourites", timeout=10).status_code == 400


def test_frontend_proxy_reaches_backend():
    frontend = os.getenv("STUDENT2_FRONTEND_URL", "http://localhost:8082").rstrip("/")
    response = requests.get(f"{frontend}/api/student-2/health", timeout=10)
    assert response.status_code == 200
    assert response.json()["service"] == "student-2-api"
    assert requests.get(f"{frontend}/health", timeout=5).status_code == 200
