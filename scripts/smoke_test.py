#!/usr/bin/env python3
"""Validate one student's microservices end to end.

Exercises full CRUD against the database API and checks that the backend/API
returns an HTMX fragment built from that data. Used by the GitHub Actions
workflows and runnable locally:

    python3 scripts/smoke_test.py 1
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

RESOURCES = {
    1: [
        (
            "trips",
            {
                "trip_name": "CI smoke trip",
                "destination": "Wellington, NZ",
                "start_date": "2026-12-01",
                "end_date": "2026-12-08",
                "traveller_id": 1,
                "budget_aud": 1234.0,
                "status": "planned",
            },
            {"status": "booked"},
            "trip_id",
        ),
    ],
}

DEFAULT_RESOURCE = (
    "records",
    {
        "title": "CI smoke record",
        "category": "smoke",
        "detail": "created by smoke_test.py",
        "created_on": "2026-08-24",
    },
    {"category": "smoke-updated"},
    "record_id",
)


class SmokeFailure(Exception):
    pass


def request(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode()
            return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"{method} {url} did not connect: {exc}") from exc


def expect(condition, message):
    if not condition:
        raise SmokeFailure(message)
    print(f"  ok  {message}")


def check_resource(db_base, resource, create_payload, update_payload, id_field):
    status, body = request("GET", f"{db_base}/{resource}")
    expect(status == 200, f"GET /{resource} returns 200")
    rows = json.loads(body)
    expect(isinstance(rows, list), f"GET /{resource} returns a list")
    expect(
        len(rows) >= 10,
        f"/{resource} is seeded with at least 10 records (found {len(rows)})",
    )

    status, body = request("POST", f"{db_base}/{resource}", create_payload)
    expect(status == 201, f"POST /{resource} creates a record (201)")
    created = json.loads(body)
    new_id = created[id_field]

    status, body = request("GET", f"{db_base}/{resource}/{new_id}")
    expect(status == 200, f"GET /{resource}/{new_id} reads it back")

    status, body = request("PUT", f"{db_base}/{resource}/{new_id}", update_payload)
    expect(status == 200, f"PUT /{resource}/{new_id} updates it")
    updated = json.loads(body)
    field, value = next(iter(update_payload.items()))
    expect(updated[field] == value, f"update actually changed {field} to {value}")

    status, _ = request("DELETE", f"{db_base}/{resource}/{new_id}")
    expect(status == 200, f"DELETE /{resource}/{new_id} removes it")

    status, _ = request("GET", f"{db_base}/{resource}/{new_id}")
    expect(status == 404, f"GET /{resource}/{new_id} is 404 after delete")


def check_cross_feature(trips_fragment):
    """student-1 stores traveller_id but does not own traveller records.

    The rendered table must show a name resolved from the shared access API,
    which proves the cross-feature read happened over HTTP. A bare "#<id>" means
    the lookup silently fell back, so the integration is not actually working.
    """
    status, body = request("GET", "http://localhost:5000/travellers")
    expect(status == 200, "shared access API serves traveller records")
    travellers = json.loads(body)
    expect(len(travellers) >= 10, f"shared access DB is seeded ({len(travellers)} travellers)")

    names = [row["full_name"] for row in travellers]
    resolved = [name for name in names if f"<td>{name}</td>" in trips_fragment]
    expect(
        bool(resolved),
        f"trip table resolves traveller names cross-service (e.g. {resolved[:1]})",
    )
    expect(
        "<td>#" not in trips_fragment,
        "no trip fell back to a raw traveller id",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("student", type=int, choices=range(1, 6))
    parser.add_argument("--host", default="localhost")
    args = parser.parse_args()

    n = args.student
    db_base = f"http://{args.host}:{5200 + n}"
    api_base = f"http://{args.host}:{5100 + n}"

    print(f"Smoke test: student-{n}")

    try:
        status, body = request("GET", f"{db_base}/health")
        expect(status == 200, "database service is healthy")

        status, body = request("GET", f"{api_base}/health")
        expect(status == 200, "backend/API service is healthy")

        for resource in RESOURCES.get(n, [DEFAULT_RESOURCE]):
            check_resource(db_base, *resource)

        listing_path = "trips" if n == 1 else "records"
        status, body = request("GET", f"{api_base}/{listing_path}")
        expect(status == 200, f"backend/API GET /{listing_path} returns 200")
        expect(
            "<table" in body or "muted" in body,
            "backend/API returns an HTML fragment, not JSON",
        )

        if n == 1:
            check_cross_feature(body)
    except SmokeFailure as failure:
        print(f"\nFAIL: {failure}")
        return 1

    print(f"\nstudent-{n} passed all checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
