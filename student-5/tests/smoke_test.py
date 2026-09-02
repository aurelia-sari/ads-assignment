#!/usr/bin/env python3
"""Feature smoke test for student-5 (Bookings & Budget, Aung Ko Khaing).

Bookings & Budget doesn't fit the generic single-resource CRUD shape the
scaffold's DEFAULT_RESOURCE assumes:

- budgets are a per-trip singleton, updated via upsert - "delete" doesn't
  make sense for a budget
- flights and hotels are read-only search endpoints with no create, update
  or delete at all
- only trip selections and search history behave like a conventional
  creatable/deletable record

This exercises each resource according to what it actually does. Invoked by
scripts/smoke_test.py's check_student_5(), and runnable directly:

    python3 student-5/tests/smoke_test.py
"""

import json
import sys
import urllib.error
import urllib.request

DB_BASE = "http://localhost:5205"
API_BASE = "http://localhost:5105/api/student-5"


class SmokeFailure(Exception):
    pass


def request(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"{method} {url} did not connect: {exc}") from exc


def expect(condition, message):
    if not condition:
        raise SmokeFailure(message)
    print(f"  ok  {message}")


def check_seed_data():
    status, body = request("GET", f"{DB_BASE}/health")
    expect(status == 200, "database service reports health")
    counts = json.loads(body).get("counts", {})

    for table in ("budgets", "flights", "hotels", "trip_selections", "search_history"):
        expect(
            counts.get(table, 0) >= 10,
            f"{table} is seeded with at least 10 records (found {counts.get(table, 0)})",
        )


def check_budget_upsert():
    status, body = request("GET", f"{API_BASE}/budgets/1")
    expect(status == 200, "GET /budgets/1 returns the seeded budget")
    original = json.loads(body)

    status, body = request(
        "PUT",
        f"{API_BASE}/budgets/1",
        {"total_budget": 9999, "flight_budget": 4000, "hotel_budget": 3000},
    )
    expect(status == 200, "PUT /budgets/1 updates the budget")
    updated = json.loads(body)
    expect(updated["total_budget"] == 9999, "the update actually changed total_budget")

    status, _ = request(
        "PUT",
        f"{API_BASE}/budgets/1",
        {
            "total_budget": original["total_budget"],
            "flight_budget": original["flight_budget"],
            "hotel_budget": original["hotel_budget"],
        },
    )
    expect(status == 200, "PUT /budgets/1 restores the original values")


def check_flight_and_hotel_search():
    status, body = request("GET", f"{API_BASE}/flights/search?destination=Bangkok")
    expect(status == 200, "GET /flights/search returns 200")
    payload = json.loads(body)
    expect("results" in payload, "flight search response has a results field")
    expect(
        len(payload["results"]) > 0,
        "flight search for Bangkok returns at least one result",
    )
    expect(
        all("recommendation_score" in row for row in payload["results"]),
        "every flight result carries a recommendation_score",
    )

    status, body = request("GET", f"{API_BASE}/hotels/search?destination=Bangkok")
    expect(status == 200, "GET /hotels/search returns 200")
    payload = json.loads(body)
    expect(
        len(payload["results"]) > 0,
        "hotel search for Bangkok returns at least one result",
    )


def check_selection_lifecycle():
    status, body = request(
        "POST",
        f"{API_BASE}/selections",
        {
            "trip_id": 1,
            "item_type": "flight",
            "item_id": 1,
            "item_name": "CI smoke selection",
            "price_aud": 123.45,
        },
    )
    expect(status == 201, "POST /selections creates a selection (201)")
    selection_id = json.loads(body)["selection_id"]

    status, body = request("GET", f"{API_BASE}/selections/1")
    expect(status == 200, "GET /selections/1 reads the trip's selections")
    ids = [row["selection_id"] for row in json.loads(body)]
    expect(selection_id in ids, "the new selection appears in the trip's list")

    status, _ = request("DELETE", f"{API_BASE}/selections/{selection_id}")
    expect(status == 200, f"DELETE /selections/{selection_id} removes it")

    status, body = request("GET", f"{API_BASE}/selections/1")
    ids = [row["selection_id"] for row in json.loads(body)]
    expect(selection_id not in ids, "the deleted selection no longer appears")


def check_search_history():
    status, body = request(
        "POST",
        f"{API_BASE}/search-history",
        {
            "trip_id": 1,
            "search_type": "flight",
            "origin": "Sydney",
            "destination": "CI smoke destination",
            "start_date": "2026-12-01",
            "end_date": "2026-12-08",
            "travellers": 1,
            "budget_aud": 1000,
            "search_query": "flight: CI smoke destination",
        },
    )
    expect(status == 201, "POST /search-history creates a record (201)")

    status, body = request("GET", f"{API_BASE}/search-history/1")
    expect(status == 200, "GET /search-history/1 returns 200")
    destinations = [row["destination"] for row in json.loads(body)]
    expect(
        "CI smoke destination" in destinations,
        "the new search appears in trip 1's search history",
    )


def main():
    print("Feature smoke test: student-5 (Bookings & Budget)")

    try:
        status, _ = request("GET", f"{DB_BASE}/health")
        expect(status == 200, "database service is healthy")

        status, _ = request("GET", f"{API_BASE}/health")
        expect(status == 200, "backend/API service is healthy")

        check_seed_data()
        check_budget_upsert()
        check_flight_and_hotel_search()
        check_selection_lifecycle()
        check_search_history()
    except SmokeFailure as failure:
        print(f"\nFAIL: {failure}")
        return 1

    print("\nstudent-5 feature smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())