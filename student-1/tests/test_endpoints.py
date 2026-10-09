"""Post-commit endpoint tests for student-1-api (Release 2, criterion 4).

Two endpoint functions of the Trips & Itinerary backend/API are tested against
the running containers, not a mock: student-1.yml starts student-1-db,
student-1-api and the frontends, then runs this file. A pass therefore means
the request really went Backend/API -> student-1-db and back.

  1. create_trip     POST /trips              (routes/trips.py)
  2. list_trip_days  GET  /trips/<id>/days    (routes/itinerary.py)

Locally, with the stack up:
    python -m pytest -v student-1/tests/test_endpoints.py

Every test creates its own uniquely named trip and deletes it afterwards
through student-1-db, so the tests never depend on or disturb the seed data.
"""

import os
import uuid

import pytest
import requests

API = os.getenv("STUDENT1_API_URL", "http://localhost:5101")
DB = os.getenv("STUDENT1_DB_URL", "http://localhost:5201")
TIMEOUT = 15

TRIP = {
    "destination": "Hobart, Australia",
    "start_date": "2026-11-02",
    "end_date": "2026-11-05",
    "traveller_id": "1",
    "budget_aud": "1450",
    "status": "planned",
}


def unique_name():
    return f"CI endpoint test {uuid.uuid4().hex[:8]}"


def find_trip_id(name):
    """Look the trip up in the database service, which owns it."""
    trips = requests.get(f"{DB}/trips", timeout=TIMEOUT).json()
    matches = [t["trip_id"] for t in trips if t["trip_name"] == name]
    return matches[0] if matches else None


@pytest.fixture
def cleanup():
    """Collects trip names to delete once the test finishes, pass or fail."""
    names = []
    yield names
    for name in names:
        trip_id = find_trip_id(name)
        if trip_id is not None:
            requests.delete(f"{DB}/trips/{trip_id}", timeout=TIMEOUT)


@pytest.fixture
def trip(cleanup):
    """A trip created directly in student-1-db, for the itinerary tests."""
    name = unique_name()
    cleanup.append(name)
    payload = {**TRIP, "trip_name": name, "traveller_id": 1, "budget_aud": 1450.0}
    response = requests.post(f"{DB}/trips", json=payload, timeout=TIMEOUT)
    assert response.status_code == 201, response.text
    return response.json()


# --- Endpoint 1: create_trip, POST /trips ------------------------------------

def test_create_trip_stores_the_trip_and_returns_the_refreshed_table(cleanup):
    name = unique_name()
    cleanup.append(name)

    response = requests.post(f"{API}/trips", data={**TRIP, "trip_name": name}, timeout=TIMEOUT)

    assert response.status_code == 201
    # The API answers HTMX with the refreshed trips table, new trip included.
    assert "<table" in response.text
    assert name in response.text
    # And the trip really reached the database service, with its fields intact.
    trip_id = find_trip_id(name)
    assert trip_id is not None
    stored = requests.get(f"{DB}/trips/{trip_id}", timeout=TIMEOUT).json()
    assert stored["destination"] == TRIP["destination"]
    assert stored["start_date"] == TRIP["start_date"]
    assert stored["budget_aud"] == 1450.0
    assert stored["status"] == "planned"


def test_create_trip_rejects_an_end_date_before_the_start_date(cleanup):
    name = unique_name()
    cleanup.append(name)
    bad = {**TRIP, "trip_name": name, "start_date": "2026-11-05", "end_date": "2026-11-02"}

    response = requests.post(f"{API}/trips", data=bad, timeout=TIMEOUT)

    assert response.status_code == 400
    assert "end_date cannot be earlier than start_date" in response.text
    assert find_trip_id(name) is None


def test_create_trip_rejects_missing_fields(cleanup):
    name = unique_name()
    cleanup.append(name)
    incomplete = {"trip_name": name, "destination": "Hobart, Australia"}

    response = requests.post(f"{API}/trips", data=incomplete, timeout=TIMEOUT)

    assert response.status_code == 400
    assert "Missing fields" in response.text
    assert find_trip_id(name) is None


# --- Endpoint 2: list_trip_days, GET /trips/<id>/days --------------------------

def test_list_trip_days_shows_each_day_of_that_trip_in_order(trip):
    for number, (date, activity) in enumerate(
        [("2026-11-02", "Salamanca Market"), ("2026-11-03", "MONA by ferry")], start=1
    ):
        response = requests.post(f"{DB}/days", json={
            "trip_id": trip["trip_id"], "day_number": number, "day_date": date,
            "location": "Hobart", "activity": activity, "notes": "",
        }, timeout=TIMEOUT)
        assert response.status_code == 201, response.text

    response = requests.get(f"{API}/trips/{trip['trip_id']}/days", timeout=TIMEOUT)

    assert response.status_code == 200
    body = response.text
    assert f"Itinerary - {trip['trip_name']}" in body
    assert body.index("Salamanca Market") < body.index("MONA by ferry")
    # The add-a-day form is scoped to this trip.
    assert f"name='trip_id' value='{trip['trip_id']}'" in body


def test_list_trip_days_for_a_trip_with_no_days_offers_to_add_one(trip):
    response = requests.get(f"{API}/trips/{trip['trip_id']}/days", timeout=TIMEOUT)

    assert response.status_code == 200
    assert "No itinerary days yet for this trip." in response.text
    assert "<form" in response.text


def test_list_trip_days_does_not_leak_days_from_other_trips(trip):
    response = requests.get(f"{API}/trips/{trip['trip_id']}/days", timeout=TIMEOUT)

    # Trip 1 in the seed data has Kyoto days. A fresh trip must show none.
    assert response.status_code == 200
    assert "Gion evening walk" not in response.text
