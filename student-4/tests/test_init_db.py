"""Unit tests for the student-4-db seed.

init_db.py runs at every container start against the existing volume, so it
must be safe to repeat, keep destination ids stable and keep saved chats.

    python -m pytest student-4/tests/test_init_db.py
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

INIT_DB = Path(__file__).resolve().parents[1] / "db" / "init_db.py"


def run_seed(data_dir):
    subprocess.run(
        [sys.executable, str(INIT_DB)],
        env={**os.environ, "DATA_DIR": str(data_dir)},
        check=True,
        capture_output=True,
    )
    return sqlite3.connect(data_dir / "student4.db")


def add_chat(conn, destination_id):
    session_id = conn.execute(
        "INSERT INTO guide_ai_chat_sessions (user_id, destination_id, created_at) "
        "VALUES (1, ?, '2026-10-01T00:00:00+00:00')",
        (destination_id,),
    ).lastrowid
    conn.execute(
        "INSERT INTO guide_ai_chat_messages (session_id, role, content, created_at) "
        "VALUES (?, 'user', 'hello', '2026-10-01T00:00:00+00:00')",
        (session_id,),
    )
    conn.commit()
    return session_id


@pytest.fixture
def seeded(tmp_path):
    conn = run_seed(tmp_path)
    yield tmp_path, conn
    conn.close()


def test_destinations_get_fixed_ids(seeded):
    _, conn = seeded
    ids = dict(conn.execute("SELECT city, id FROM destinations"))
    assert ids["Sydney"] == 1
    assert ids["Melbourne"] == 2
    assert ids["Alice Springs"] == 13


def test_reseed_is_idempotent(seeded):
    data_dir, conn = seeded
    tables = ("destinations", "currency_infos", "transportation_infos", "visa_requirements",
              "weather_infos", "safety_infos", "feature_redirect_map")
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    conn.close()

    conn = run_seed(data_dir)
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    conn.close()
    assert after == before


def test_reseed_keeps_saved_chats(seeded):
    data_dir, conn = seeded
    session_id = add_chat(conn, 1)
    conn.close()

    conn = run_seed(data_dir)
    row = conn.execute(
        "SELECT d.city FROM guide_ai_chat_sessions s JOIN destinations d ON d.id = s.destination_id "
        "WHERE s.id = ?",
        (session_id,),
    ).fetchone()
    messages = conn.execute(
        "SELECT COUNT(*) FROM guide_ai_chat_messages WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    conn.close()
    assert row == ("Sydney",)
    assert messages == 1


def test_reseed_updates_a_changed_destination(seeded):
    data_dir, conn = seeded
    conn.execute("UPDATE destinations SET city = 'Old name' WHERE id = 1")
    conn.commit()
    conn.close()

    conn = run_seed(data_dir)
    city = conn.execute("SELECT city FROM destinations WHERE id = 1").fetchone()[0]
    conn.close()
    assert city == "Sydney"


def test_reseed_removes_a_dropped_destination_and_its_chats(seeded):
    data_dir, conn = seeded
    conn.execute(
        "INSERT INTO destinations (id, country, city, region) VALUES (999, 'Nowhere', 'Gone', 'None')"
    )
    kept = add_chat(conn, 1)
    dropped = add_chat(conn, 999)
    conn.close()

    conn = run_seed(data_dir)
    sessions = {row[0] for row in conn.execute("SELECT id FROM guide_ai_chat_sessions")}
    orphan_messages = conn.execute(
        "SELECT COUNT(*) FROM guide_ai_chat_messages WHERE session_id = ?", (dropped,)
    ).fetchone()[0]
    gone = conn.execute("SELECT COUNT(*) FROM destinations WHERE id = 999").fetchone()[0]
    conn.close()
    assert kept in sessions
    assert dropped not in sessions
    assert orphan_messages == 0
    assert gone == 0
