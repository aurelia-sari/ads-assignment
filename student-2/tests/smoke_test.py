"""
Deterministic smoke test for student-2 (Attractions & Dining).

Exercises the currently implemented `places`, `favourites`, and
`recommendations` CRUD and validation behaviour. No LLM involved -
this is a plain pass/fail regression test.
"""

import os
import sys
import json

import requests

API_BASE = os.getenv("STUDENT2_API_URL", "http://localhost:5102")
DB_BASE = os.getenv("STUDENT2_DB_URL", "http://localhost:5202")

TEST_USER_ID = 15
OTHER_USER_ID = 999999

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

    # user_id is now required when favourites are requested
    # through the Student 2 API.
    status, _ = _call(
        "GET",
        f"{API_BASE}/favourites",
    )
    expect(
        status == 400,
        "GET /favourites without user_id returns 400",
    )

    status, _ = _call(
        "GET",
        f"{API_BASE}/favourites",
        params={"user_id": TEST_USER_ID},
    )
    expect(
        status == 200,
        "GET /favourites?user_id=<id> returns 200",
    )

    status, db_response = _call(
        "GET",
        f"{DB_BASE}/places",
    )
    expect(
        status == 200,
        "GET /places (database) returns 200",
    )

    rows = db_response.json()

    expect(
        bool(rows),
        "at least one seeded place is available to favourite",
    )

    sample_place_id = rows[0]["id"]

    # Create favourite for the test user.
    status, _ = _call(
        "POST",
        f"{API_BASE}/favourites",
        json={
            "user_id": TEST_USER_ID,
            "place_id": sample_place_id,
        },
    )
    expect(
        status == 201,
        "POST /favourites valid user_id/place_id returns 201",
    )

    # Same user + same place must be rejected.
    status, _ = _call(
        "POST",
        f"{API_BASE}/favourites",
        json={
            "user_id": TEST_USER_ID,
            "place_id": sample_place_id,
        },
    )
    expect(
        status == 400,
        "POST /favourites duplicate returns 400",
    )

    # Unknown place.
    status, _ = _call(
        "POST",
        f"{API_BASE}/favourites",
        json={
            "user_id": TEST_USER_ID,
            "place_id": 999999,
        },
    )
    expect(
        status == 404,
        "POST /favourites unknown place_id returns 404",
    )

    # Missing user_id.
    status, _ = _call(
        "POST",
        f"{API_BASE}/favourites",
        json={
            "place_id": sample_place_id,
        },
    )
    expect(
        status == 400,
        "POST /favourites missing user_id returns 400",
    )

    # Missing place_id.
    status, _ = _call(
        "POST",
        f"{API_BASE}/favourites",
        json={
            "user_id": TEST_USER_ID,
        },
    )
    expect(
        status == 400,
        "POST /favourites missing place_id returns 400",
    )

    # Find the favourite directly through the database API.
    status, db_response = _call(
        "GET",
        f"{DB_BASE}/favourites",
        params={"user_id": TEST_USER_ID},
    )
    expect(
        status == 200,
        "GET /favourites (database) returns 200",
    )

    favourite_id = next(
        (
            row["id"]
            for row in db_response.json()
            if row["user_id"] == TEST_USER_ID
            and row["place_id"] == sample_place_id
        ),
        None,
    )

    expect(
        favourite_id is not None,
        "created test favourite can be located",
    )

    # A different user must not be able to delete it.
    status, response = _call(
        "DELETE",
        f"{API_BASE}/favourites/{favourite_id}",
        json={
            "user_id": 999999,
        },
    )

    print(
        f"  DEBUG wrong-user delete: "
        f"status={status}, body={response.text}"
    )

    expect(
        status == 404,
        "DELETE /favourites/<id> by another user returns 404",
    )

    # Owner can delete it.
    status, _ = _call(
        "DELETE",
        f"{API_BASE}/favourites/{favourite_id}",
        json={
            "user_id": TEST_USER_ID,
        },
    )
    expect(
        status == 200,
        "DELETE /favourites/<id> by owner returns 200",
    )

    # Deleting the same favourite again should fail.
    status, _ = _call(
        "DELETE",
        f"{API_BASE}/favourites/{favourite_id}",
        json={
            "user_id": TEST_USER_ID,
        },
    )
    expect(
        status == 404,
        "DELETE /favourites/<id> again returns 404",
    )
    
    # --- Recommendations ------------------------------------------------
    status, db_response = _call("GET", f"{DB_BASE}/recommendations")
    expect(status == 200, "GET /recommendations returns 200")

    before_count = len(db_response.json())

    recommendation_payload = {
        "user_id": TEST_USER_ID,
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
        saved_recommendation.get("user_id") == TEST_USER_ID,
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

    # Anonymous recommendation should also be accepted.
    anonymous_payload = {
        "user_id": None,
        "question": "Recommend an attraction.",
        "preferences": None,
        "location": "Sydney",
        "recommendation_result": json.dumps(
            {
                "answer": "Anonymous smoke test recommendation",
                "place_ids": [1],
            }
        ),
    }

    status, anonymous_response = _call(
        "POST",
        f"{DB_BASE}/recommendations",
        json=anonymous_payload,
    )

    expect(
        status == 201,
        "POST /recommendations without user_id returns 201",
    )

    anonymous_id = anonymous_response.json().get("id")

    expect(
        anonymous_id is not None,
        "anonymous recommendation returns an id",
    )

    status, anonymous_response = _call(
        "GET",
        f"{DB_BASE}/recommendations/{anonymous_id}",
    )

    expect(
        status == 200,
        "GET anonymous recommendation returns 200",
    )

    anonymous_saved = anonymous_response.json()

    expect(
        anonymous_saved.get("user_id") is None,
        "anonymous recommendation stores NULL user_id",
    )

    # Clean up anonymous recommendation.
    status, _ = _call(
        "DELETE",
        f"{DB_BASE}/recommendations/{anonymous_id}",
    )

    expect(
        status == 200,
        "DELETE anonymous recommendation returns 200",
    )


def main():
    print(
        "Smoke test: student-2 places, favourites & recommendations"
    )

    try:
        run_checks()
    except SmokeFailure as failure:
        print(f"\nFAIL: {failure}")
        return 1

    print(
        "\nstudent-2 places, favourites & recommendations "
        "passed all checks."
    )
    return 0    


if __name__ == "__main__":
    sys.exit(main())
