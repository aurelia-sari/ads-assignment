"""CRUD tests for the student-3 database service (trip_posts, connect_requests).

    python -m pytest student-3/tests/test_db_service.py
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

DB_APP = Path(__file__).resolve().parents[1] / "db" / "app.py"

SCHEMA = """
CREATE TABLE trip_posts (
    post_id INTEGER PRIMARY KEY, traveller_id INTEGER NOT NULL, destination TEXT NOT NULL,
    start_date TEXT NOT NULL, end_date TEXT NOT NULL, travel_style TEXT NOT NULL,
    note TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL);
CREATE TABLE connect_requests (
    request_id INTEGER PRIMARY KEY, from_traveller_id INTEGER NOT NULL, to_post_id INTEGER NOT NULL,
    message TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
    FOREIGN KEY (to_post_id) REFERENCES trip_posts (post_id) ON DELETE CASCADE);
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Load by path under a unique name: the API service is also called app.py.
    spec = importlib.util.spec_from_file_location("student3_db_app", DB_APP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    db_file = tmp_path / "student3.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setattr(module, "DATABASE_NAME", str(db_file))
    return module.app.test_client()


def _post(client, **overrides):
    payload = {"traveller_id": 1, "destination": "Bali, Indonesia", "start_date": "2026-10-12",
               "end_date": "2026-10-19", "travel_style": "hiking"}
    payload.update(overrides)
    return client.post("/trip_posts", json=payload)


def _request(client, post_id):
    return client.post("/connect_requests",
                       json={"from_traveller_id": 2, "to_post_id": post_id, "message": "hi"})


def test_create_then_read_a_trip_post(client):
    created = _post(client)
    assert created.status_code == 201
    fetched = client.get(f"/trip_posts/{created.get_json()['post_id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["destination"] == "Bali, Indonesia"


def test_create_rejects_missing_fields(client):
    response = client.post("/trip_posts", json={"destination": "Bali"})
    assert response.status_code == 400
    assert "Missing fields" in response.get_json()["error"]


def test_create_rejects_end_before_start(client):
    assert _post(client, start_date="2026-10-19", end_date="2026-10-12").status_code == 400


def test_update_changes_the_trip_post(client):
    post_id = _post(client).get_json()["post_id"]
    response = client.put(f"/trip_posts/{post_id}", json={"destination": "Ubud, Bali"})
    assert response.status_code == 200
    assert response.get_json()["destination"] == "Ubud, Bali"


def test_update_with_no_fields_is_rejected(client):
    post_id = _post(client).get_json()["post_id"]
    assert client.put(f"/trip_posts/{post_id}", json={}).status_code == 400


def test_update_and_delete_unknown_post_return_404(client):
    assert client.put("/trip_posts/999", json={"note": "x"}).status_code == 404
    assert client.delete("/trip_posts/999").status_code == 404


def test_list_filters_by_destination_and_status(client):
    _post(client, destination="Kyoto, Japan")
    _post(client, destination="Lisbon, Portugal", status="closed")
    kyoto = client.get("/trip_posts", query_string={"destination": "kyoto"}).get_json()
    closed = client.get("/trip_posts", query_string={"status": "closed"}).get_json()
    assert [p["destination"] for p in kyoto] == ["Kyoto, Japan"]
    assert [p["destination"] for p in closed] == ["Lisbon, Portugal"]


def test_connect_request_needs_an_existing_post(client):
    assert _request(client, 999).status_code == 404


def test_connect_request_status_is_validated(client):
    post_id = _post(client).get_json()["post_id"]
    request_id = _request(client, post_id).get_json()["request_id"]
    assert client.put(f"/connect_requests/{request_id}", json={"status": "bogus"}).status_code == 400
    assert client.put(f"/connect_requests/{request_id}", json={"status": "accepted"}).status_code == 200


def test_deleting_a_post_removes_its_connect_requests(client):
    post_id = _post(client).get_json()["post_id"]
    _request(client, post_id)
    assert client.delete(f"/trip_posts/{post_id}").status_code == 200
    assert client.get("/connect_requests", query_string={"to_post_id": post_id}).get_json() == []