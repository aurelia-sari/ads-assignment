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
from zoneinfo import ZoneInfo

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
    assert ids == {
        "Sydney": 1, "Melbourne": 2, "Brisbane": 3, "Perth": 4, "Cairns": 7,
        "Tokyo": 14, "Osaka": 15, "Sapporo": 16, "Kyoto": 17, "Nara": 18,
    }


def test_every_destination_has_coordinates(seeded):
    _, conn = seeded
    missing = conn.execute(
        "SELECT city FROM destinations WHERE latitude IS NULL OR longitude IS NULL"
    ).fetchall()
    assert missing == []


def test_every_destination_has_a_real_timezone(seeded):
    _, conn = seeded
    zones = dict(conn.execute("SELECT city, timezone FROM destinations"))
    assert zones["Perth"] == "Australia/Perth"
    assert zones["Cairns"] == "Australia/Brisbane"
    assert zones["Sapporo"] == "Asia/Tokyo"
    for zone in zones.values():
        ZoneInfo(zone)


def test_kansai_cities_have_their_own_jma_weather(seeded):
    _, conn = seeded
    rows = conn.execute(
        "SELECT d.city, w.month, w.avg_temp, w.rainfall FROM weather_infos w "
        "JOIN destinations d ON d.id = w.destination_id WHERE d.city IN ('Osaka', 'Kyoto', 'Nara')"
    ).fetchall()
    by_city = {}
    for city, month, avg_temp, rainfall in rows:
        by_city.setdefault(city, {})[month] = (avg_temp, rainfall)
    assert by_city["Kyoto"]["July"] == (32, 224)
    assert by_city["Osaka"]["September"] == (30, 153)
    assert by_city["Nara"]["August"] == (33, 128)
    assert len({tuple(sorted(months.items())) for months in by_city.values()}) == 3


@pytest.mark.parametrize("city, month, figures", [
    ("Sydney", "July", (18, 80)),
    ("Melbourne", "June", (15, 50)),
    ("Brisbane", "February", (30, 182)),
    ("Perth", "July", (19, 147)),
    ("Cairns", "February", (32, 476)),
])
def test_australian_cities_use_bureau_of_meteorology_averages(seeded, city, month, figures):
    _, conn = seeded
    row = conn.execute(
        "SELECT w.avg_temp, w.rainfall FROM weather_infos w JOIN destinations d ON d.id = w.destination_id "
        "WHERE d.city = ? AND w.month = ?",
        (city, month),
    ).fetchone()
    assert row == figures


def test_currency_follows_the_country(seeded):
    _, conn = seeded
    codes = dict(conn.execute(
        "SELECT d.city, c.currency_code FROM currency_infos c JOIN destinations d ON d.id = c.destination_id"
    ))
    assert codes["Sydney"] == "AUD"
    assert codes["Tokyo"] == "JPY"


def test_only_student_5_cities_can_book_flights(seeded):
    _, conn = seeded
    bookable = {row[0] for row in conn.execute(
        "SELECT d.city FROM transportation_infos t JOIN destinations d ON d.id = t.destination_id "
        "WHERE t.bookable = 1"
    )}
    assert bookable == {"Sydney", "Melbourne", "Brisbane", "Perth", "Tokyo", "Osaka", "Sapporo"}
    assert conn.execute(
        "SELECT COUNT(*) FROM transportation_infos WHERE bookable = 1 AND type != 'flights'"
    ).fetchone()[0] == 0


def test_cities_without_an_airport_have_no_flights_tab(seeded):
    _, conn = seeded
    types = {row[0] for row in conn.execute(
        "SELECT t.type FROM transportation_infos t JOIN destinations d ON d.id = t.destination_id "
        "WHERE d.city = 'Nara'"
    )}
    assert types == {"train", "taxi", "rental"}


def test_seed_upgrades_a_release_1_database(tmp_path):
    # The shape an existing student_4_db_data volume has before this change.
    conn = sqlite3.connect(tmp_path / "student4.db")
    conn.executescript("""
        CREATE TABLE destinations (id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL, city TEXT NOT NULL, region TEXT NOT NULL);
        CREATE TABLE transportation_infos (id INTEGER PRIMARY KEY AUTOINCREMENT,
            destination_id INTEGER NOT NULL, type TEXT NOT NULL,
            description TEXT NOT NULL, tips TEXT NOT NULL);
        INSERT INTO destinations VALUES (1, 'Australia', 'Sydney', 'New South Wales');
        INSERT INTO destinations VALUES (13, 'Australia', 'Alice Springs', 'Northern Territory');
    """)
    conn.commit()
    conn.close()

    conn = run_seed(tmp_path)
    cities = dict(conn.execute("SELECT id, city FROM destinations"))
    bookable = conn.execute("SELECT COUNT(*) FROM transportation_infos WHERE bookable = 1").fetchone()[0]
    sydney_zone = conn.execute("SELECT timezone FROM destinations WHERE id = 1").fetchone()[0]
    conn.close()
    assert cities[1] == "Sydney"
    assert sydney_zone == "Australia/Sydney"
    assert 13 not in cities
    assert bookable == 7


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
