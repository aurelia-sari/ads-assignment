"""
Deterministic smoke test for student-2 (Attractions & Dining).

Exercises the real, currently-implemented `places` and `favourites` CRUD and
validation behaviour end to end through student-2-api. No LLM involved -
this is a plain pass/fail regression test:

    docker compose up -d student-2-db student-2-api
    python3 student-2/tests/smoke_test.py

Every check that creates data also deletes it again, so re-running this
script never leaves stray rows behind in the shared docker volume.

Override the target host with STUDENT2_API_URL / STUDENT2_DB_URL if the
services are not on their default ports.
"""

import os
import sys
import json

import requests

API_BASE = os.getenv("STUDENT2_API_URL", "http://localhost:5102")
DB_BASE = os.getenv("STUDENT2_DB_URL", "http://localhost:5202")


class SmokeFailure(Exception):
    pass


def _call(method, url, timeout=5, **kwargs):
    try:
        response = requests.request(method, url, timeout=timeout, **kwargs)
        return response.status_code, response
    except requests.RequestException as exc:
        raise SmokeFailure(f"{method} {url} did not connect: {exc}") from exc


def expect(condition, message):
    if not condition:
        raise SmokeFailure(message)
    print(f"  ok  {message}")


def run_checks():
    """Run every check in order. Raises SmokeFailure on the first failure."""

    status, _ = _call("GET", f"{API_BASE}/health")
    expect(status == 200, "GET /health returns 200")

    # --- Places -------------------------------------------------------
    status, _ = _call("GET", f"{API_BASE}/places")
    expect(status == 200, "GET /places returns 200")

    status, _ = _call("POST", f"{API_BASE}/places", data={"category": "attraction"})
    expect(status == 400, "POST /places missing name/address returns 400")

    status, _ = _call(
        "POST", f"{API_BASE}/places",
        data={"name": "Smoke Test Place", "category": "bogus", "address": "1 Smoke St"},
    )
    expect(status == 400, "POST /places invalid category returns 400")

    status, _ = _call(
        "POST", f"{API_BASE}/places",
        data={
            "name": "Smoke Test Place", "category": "attraction",
            "address": "1 Smoke St", "rating": "9",
        },
    )
    expect(status == 400, "POST /places rating out of range returns 400")

    status, _ = _call(
        "POST", f"{API_BASE}/places",
        data={
            "name": "Smoke Test Place", "category": "attraction", "address": "1 Smoke St",
            "rating": "4.0", "price_range": "0", "description": "created by smoke_test.py",
        },
    )
    expect(status == 201, "POST /places valid create returns 201")

    # The create response is an HTML fragment, so the new row's id is looked
    # up from the database service by name.
    status, db_response = _call("GET", f"{DB_BASE}/places")
    expect(status == 200, "GET /places (database) returns 200")
    place_id = next(
        (row["id"] for row in db_response.json() if row["name"] == "Smoke Test Place"), None
    )
    expect(place_id is not None, "created test place can be located by name")

    status, _ = _call("GET", f"{API_BASE}/places/edit", params={"id": 999999})
    expect(status == 404, "GET /places/edit?id=<unknown> returns 404")

    status, _ = _call("GET", f"{API_BASE}/places/edit", params={"id": place_id})
    expect(status == 200, "GET /places/edit?id=<created> returns 200")

    status, _ = _call("PUT", f"{API_BASE}/places/{place_id}", data={"category": "bogus"})
    expect(status == 400, "PUT /places/<id> invalid category returns 400")

    status, _ = _call(
        "PUT", f"{API_BASE}/places/{place_id}", data={"rating": "3.5", "price_range": "30"}
    )
    expect(status == 200, "PUT /places/<id> valid update returns 200")

    status, _ = _call("DELETE", f"{API_BASE}/places/{place_id}")
    expect(status == 200, "DELETE /places/<id> returns 200")

    status, _ = _call("DELETE", f"{API_BASE}/places/{place_id}")
    expect(status == 404, "DELETE /places/<id> again returns 404")

    # --- Favourites -----------------------------------------------------
    status, _ = _call("GET", f"{API_BASE}/favourites")
    expect(status == 200, "GET /favourites returns 200")

    status, db_response = _call("GET", f"{DB_BASE}/places")
    expect(status == 200, "GET /places (database) returns 200")
    rows = db_response.json()
    expect(bool(rows), "at least one seeded place is available to favourite")
    sample_place_id = rows[0]["id"]

    status, _ = _call("POST", f"{API_BASE}/favourites", data={"place_id": str(sample_place_id)})
    expect(status == 201, "POST /favourites valid place_id returns 201")

    status, _ = _call("POST", f"{API_BASE}/favourites", data={"place_id": str(sample_place_id)})
    expect(status == 400, "POST /favourites duplicate returns 400")

    status, _ = _call("POST", f"{API_BASE}/favourites", data={"place_id": "999999"})
    expect(status == 404, "POST /favourites unknown place_id returns 404")

    status, _ = _call("POST", f"{API_BASE}/favourites", data={})
    expect(status == 400, "POST /favourites missing place_id returns 400")

    status, db_response = _call("GET", f"{DB_BASE}/favourites")
    expect(status == 200, "GET /favourites (database) returns 200")
    favourite_id = next(
        (
            row["id"] for row in db_response.json()
            if row["user_id"] == "guest" and row["place_id"] == sample_place_id
        ),
        None,
    )
    expect(favourite_id is not None, "created test favourite can be located")

    status, _ = _call("DELETE", f"{API_BASE}/favourites/{favourite_id}")
    expect(status == 200, "DELETE /favourites/<id> returns 200")

    status, _ = _call("DELETE", f"{API_BASE}/favourites/{favourite_id}")
    expect(status == 404, "DELETE /favourites/<id> again returns 404")
    
    # --- Recommendations ------------------------------------------------
    status, db_response = _call("GET", f"{DB_BASE}/recommendations")
    expect(status == 200, "GET /recommendations returns 200")

    before_count = len(db_response.json())

    recommendation_payload = {
        "user_id": "smoke-test-user",
        "question": "Recommend one cheap restaurant.",
        "preferences": None,
        "location": "Sydney",
        "recommendation_result": json.dumps(
            {
                "answer": "Smoke test recommendation",
                "place_ids": [15],
            }
        ),
    }

    status, create_response = _call(
        "POST",
        f"{DB_BASE}/recommendations",
        json=recommendation_payload,
    )
    expect(
        status == 201,
        "POST /recommendations valid create returns 201",
    )

    recommendation_id = create_response.json().get("id")

    expect(
        recommendation_id is not None,
        "created recommendation returns an id",
    )

    # Read the recommendation by ID.
    status, recommendation_response = _call(
        "GET",
        f"{DB_BASE}/recommendations/{recommendation_id}",
    )
    expect(
        status == 200,
        "GET /recommendations/<id> returns 200",
    )

    saved_recommendation = recommendation_response.json()

    expect(
        saved_recommendation.get("user_id") == "smoke-test-user",
        "created recommendation stores correct user_id",
    )

    expect(
        saved_recommendation.get("question")
        == "Recommend one cheap restaurant.",
        "created recommendation stores correct question",
    )

    expect(
        saved_recommendation.get("location") == "Sydney",
        "created recommendation stores correct location",
    )

    saved_result = json.loads(
        saved_recommendation["recommendation_result"]
    )

    expect(
        saved_result.get("answer") == "Smoke test recommendation",
        "created recommendation stores correct answer",
    )

    expect(
        saved_result.get("place_ids") == [15],
        "created recommendation stores correct place_ids",
    )

    # Unknown recommendation should return 404.
    status, _ = _call(
        "GET",
        f"{DB_BASE}/recommendations/999999",
    )
    expect(
        status == 404,
        "GET /recommendations/<unknown> returns 404",
    )

    # Make sure the created recommendation appears in the collection.
    status, db_response = _call(
        "GET",
        f"{DB_BASE}/recommendations",
    )
    expect(
        status == 200,
        "GET /recommendations after create returns 200",
    )

    recommendations = db_response.json()

    expect(
        any(
            row.get("id") == recommendation_id
            for row in recommendations
        ),
        "created recommendation can be located",
    )

    expect(
        len(recommendations) == before_count + 1,
        "recommendation count increases after create",
    )

    # Clean up so the smoke test is safe to run repeatedly.
    status, _ = _call(
        "DELETE",
        f"{DB_BASE}/recommendations/{recommendation_id}",
    )
    expect(
        status == 200,
        "DELETE /recommendations/<id> returns 200",
    )

    status, _ = _call(
        "DELETE",
        f"{DB_BASE}/recommendations/{recommendation_id}",
    )
    expect(
        status == 404,
        "DELETE /recommendations/<id> again returns 404",
    )


def main():
    print("Smoke test: student-2 places & favourites")
    try:
        run_checks()
    except SmokeFailure as failure:
        print(f"\nFAIL: {failure}")
        return 1
    print("\nstudent-2 places & favourites passed all checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
