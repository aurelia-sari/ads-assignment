"""Feature-specific smoke test for student-3 (Travel Mate, Tanishpreet Kour).
 
Travel Mate has two resources with different shapes (trip_posts and
connect_requests, the latter only creatable/updatable/deletable in relation
to an existing trip_post) plus an AI-mode match-suggest step, so it doesn't
fit scripts/smoke_test.py's single generic CRUD-on-one-resource assumption.
This mirrors the override pattern already used by students 2, 4, and 5.

Runnable locally:

    python3 student-3/tests/smoke_test.py
"""
 
import json
import sys
import urllib.error
import urllib.request
 
DB_BASE = "http://localhost:5203"
API_BASE = "http://localhost:5103"
FRONTEND_BASE = "http://localhost:8083"
 
 
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
 
 
def check_trip_posts_crud():
    status, body = request("GET", f"{DB_BASE}/trip_posts")
    expect(status == 200, "GET /trip_posts returns 200")
    rows = json.loads(body)
    expect(isinstance(rows, list), "GET /trip_posts returns a list")
    expect(len(rows) >= 10, f"/trip_posts is seeded with at least 10 records (found {len(rows)})")
 
    create_payload = {
        "traveller_id": 1,
        "destination": "CI Smoke City",
        "start_date": "2026-12-01",
        "end_date": "2026-12-08",
        "travel_style": "smoke testing",
        "note": "created by smoke_test.py",
        "status": "open",
    }
    status, body = request("POST", f"{DB_BASE}/trip_posts", create_payload)
    expect(status == 201, "POST /trip_posts creates a record (201)")
    created = json.loads(body)
    post_id = created["post_id"]
 
    status, body = request("GET", f"{DB_BASE}/trip_posts/{post_id}")
    expect(status == 200, f"GET /trip_posts/{post_id} reads it back")
 
    status, body = request("PUT", f"{DB_BASE}/trip_posts/{post_id}", {"travel_style": "updated style"})
    expect(status == 200, f"PUT /trip_posts/{post_id} updates it")
    updated = json.loads(body)
    expect(updated["travel_style"] == "updated style", "update actually changed travel_style")
 
    status, _ = request("DELETE", f"{DB_BASE}/trip_posts/{post_id}")
    expect(status == 200, f"DELETE /trip_posts/{post_id} removes it")
 
    status, _ = request("GET", f"{DB_BASE}/trip_posts/{post_id}")
    expect(status == 404, f"GET /trip_posts/{post_id} is 404 after delete")
 
 
def check_connect_requests_read():
    status, body = request("GET", f"{DB_BASE}/connect_requests")
    expect(status == 200, "GET /connect_requests returns 200")
    rows = json.loads(body)
    expect(isinstance(rows, list), "GET /connect_requests returns a list")
    expect(len(rows) >= 10, f"/connect_requests is seeded with at least 10 records (found {len(rows)})")
 
 
def check_api_wiring():
    status, body = request("GET", f"{API_BASE}/trips")
    expect(status == 200, "backend/API GET /trips returns 200")
    expect(
        "card" in body or "muted" in body,
        "backend/API returns an HTML fragment, not JSON",
    )
 
 
def check_frontend_wiring():
    status, body = request("GET", f"{FRONTEND_BASE}/")
    expect(status == 200, "frontend serves its page")
 
    hx_attributes = sum(body.count(f"hx-{verb}") for verb in ("get", "post", "put", "delete"))
    expect(hx_attributes > 0, f"page has HTMX attributes ({hx_attributes} found)")
    expect("/api/student-3/" in body, "page calls its own API (/api/student-3/)")
    expect("/shared/css/theme.css" in body, "page uses the shared CSS theme")
 
 
def main():
    print("Smoke test: student-3 (Travel Mate)")
    try:
        status, _ = request("GET", f"{DB_BASE}/health")
        expect(status == 200, "database service is healthy")
 
        status, _ = request("GET", f"{API_BASE}/health")
        expect(status == 200, "backend/API service is healthy")
 
        check_trip_posts_crud()
        check_connect_requests_read()
        check_api_wiring()
        check_frontend_wiring()
    except SmokeFailure as failure:
        print(f"\nFAIL: {failure}")
        return 1
 
    print("\nstudent-3 passed all checks.")
    return 0
 
 
if __name__ == "__main__":
    sys.exit(main())