"""Post-commit endpoint tests for student-5-api (Release 2, criterion 4).

Two endpoint functions of the Bookings & Budget backend/API are tested against
the running containers: student-5.yml starts student-5-db and student-5-api,
then runs this file, so a pass means Backend/API -> student-5-db and back.

  1. update_budget  PUT  /budgets/<trip_id>  (api/app.py)
  2. add_selection  POST /selections         (api/app.py)

Locally, with the stack up:
    python -m pytest -v student-5/tests/test_endpoints.py

Each test restores or deletes whatever it changes, so seed data is untouched.
"""

import os

import pytest
import requests

API = os.getenv("STUDENT5_API_URL", "http://localhost:5105")
TIMEOUT = 15


@pytest.fixture
def budget_backup():
    """Remember trip 1's budget and put it back afterwards."""
    original = requests.get(f"{API}/budgets/1", timeout=TIMEOUT).json()
    yield original
    requests.put(
        f"{API}/budgets/1",
        json={
            "total_budget": original["total_budget"],
            "flight_budget": original["flight_budget"],
            "hotel_budget": original["hotel_budget"],
        },
        timeout=TIMEOUT,
    )


@pytest.fixture
def created_ids():
    ids = []
    yield ids
    for selection_id in ids:
        requests.delete(f"{API}/selections/{selection_id}", timeout=TIMEOUT)


def test_update_budget_changes_and_persists(budget_backup):
    new = {"total_budget": 7777, "flight_budget": 3000, "hotel_budget": 2500}
    response = requests.put(f"{API}/budgets/1", json=new, timeout=TIMEOUT)
    assert response.status_code == 200
    assert response.json()["total_budget"] == 7777

    # A fresh GET proves it reached the database, not just the response body.
    stored = requests.get(f"{API}/budgets/1", timeout=TIMEOUT).json()
    assert stored["total_budget"] == 7777
    assert stored["flight_budget"] == 3000
    assert stored["hotel_budget"] == 2500


def test_add_selection_creates_record(created_ids):
    payload = {
        "trip_id": 1,
        "item_type": "flight",
        "item_id": 1,
        "item_name": "CI endpoint test selection",
        "price_aud": 321.5,
    }
    response = requests.post(f"{API}/selections", json=payload, timeout=TIMEOUT)
    assert response.status_code == 201
    selection_id = response.json()["selection_id"]
    created_ids.append(selection_id)

    listed = requests.get(f"{API}/selections/1", timeout=TIMEOUT).json()
    assert selection_id in [row["selection_id"] for row in listed]


def test_add_selection_rejects_missing_fields():
    response = requests.post(f"{API}/selections", json={"trip_id": 1}, timeout=TIMEOUT)
    assert response.status_code == 400
    assert "Missing fields" in response.json()["error"]
