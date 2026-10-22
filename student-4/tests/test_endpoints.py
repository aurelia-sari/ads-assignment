"""Post-commit endpoint tests for the student-4 backend/API.

Run by the student-4 workflow against the started containers. They exercise
exactly two endpoint functions, list_guides (GET /guides) and start
(POST /ai/agents), through the real HTTP interface and the seeded database.

    docker compose up -d student-4-db student-4-api shared-api shared-db mailpit
    python -m pytest student-4/tests/test_endpoints.py
"""

import os

import pytest
import requests

API = os.getenv("STUDENT4_API_URL", "http://localhost:5104")
TIMEOUT = 10

# With Multi-Agent switched on, POST /ai/agents starts a real workflow, which
# needs the host AI services. The disabled path is only asserted when it is off.
AGENTS_OFF = os.getenv("MULTI_AGENT_ENABLED", "true").lower() in ("false", "0", "no")


def test_list_guides_returns_every_seeded_city():
    response = requests.get(f"{API}/guides", timeout=TIMEOUT)

    assert response.status_code == 200
    for name in ("Australia", "Japan", "Sydney", "Kyoto"):
        assert name in response.text


def test_list_guides_search_narrows_to_the_matching_country():
    response = requests.get(f"{API}/guides", params={"query": "Japan"}, timeout=TIMEOUT)

    assert response.status_code == 200
    assert "Kyoto" in response.text
    assert "Sydney" not in response.text


def test_list_guides_search_with_no_match_says_so():
    response = requests.get(f"{API}/guides", params={"query": "zzzz"}, timeout=TIMEOUT)

    assert response.status_code == 200
    assert "No cities or countries match" in response.text


def test_start_agents_requires_a_task():
    response = requests.post(f"{API}/ai/agents", data={"task": " ", "city": "Kyoto"}, timeout=TIMEOUT)

    assert response.status_code == 400
    assert "Describe the task" in response.text


@pytest.mark.skipif(not AGENTS_OFF, reason="MULTI_AGENT_ENABLED is on, so this would start a real workflow")
def test_start_agents_reports_switched_off_without_calling_the_server():
    response = requests.post(
        f"{API}/ai/agents", data={"task": "Brief me on Kyoto", "city": "Kyoto"}, timeout=TIMEOUT
    )

    assert response.status_code == 200
    assert "MULTI_AGENT_ENABLED=false" in response.text
