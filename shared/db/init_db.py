"""Create and seed the shared access database.

The shared database owns only cross-cutting access data: the traveller
accounts every feature needs to resolve a traveller_id, plus (added for the
Account & Dashboard sign-up feature) `users` and `access_logs` - the same
kind of cross-cutting data, since a user's id and sign-in state are things
every feature may need, not just Account & Dashboard. Feature-specific data
still lives in each student's own database microservice.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "shared.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS travellers (
    traveller_id   INTEGER PRIMARY KEY,
    full_name      TEXT NOT NULL,
    email          TEXT NOT NULL UNIQUE,
    home_city      TEXT NOT NULL,
    member_since   TEXT NOT NULL
)
""")

cursor.execute("DELETE FROM travellers")

travellers = [
    (1,  "Amara Okafor",     "amara.okafor@example.com",   "Sydney",     "2024-02-11"),
    (2,  "Ben Nguyen",       "ben.nguyen@example.com",     "Melbourne",  "2024-03-02"),
    (3,  "Chiara Rossi",     "chiara.rossi@example.com",   "Brisbane",   "2024-04-19"),
    (4,  "Daniel Park",      "daniel.park@example.com",    "Perth",      "2024-05-27"),
    (5,  "Elif Demir",       "elif.demir@example.com",     "Adelaide",   "2024-06-08"),
    (6,  "Farhan Iqbal",     "farhan.iqbal@example.com",   "Canberra",   "2024-07-14"),
    (7,  "Grace Liu",        "grace.liu@example.com",      "Hobart",     "2024-08-30"),
    (8,  "Hugo Martins",     "hugo.martins@example.com",   "Darwin",     "2024-09-21"),
    (9,  "Ines Fernandez",   "ines.fernandez@example.com", "Sydney",     "2024-10-05"),
    (10, "Jonah Whitfield",  "jonah.whitfield@example.com","Melbourne",  "2024-11-17"),
    (11, "Keiko Tanaka",     "keiko.tanaka@example.com",   "Gold Coast", "2025-01-23"),
    (12, "Liam O'Connor",    "liam.oconnor@example.com",   "Newcastle",  "2025-02-09"),
]

cursor.executemany(
    """
    INSERT INTO travellers (traveller_id, full_name, email, home_city, member_since)
    VALUES (?, ?, ?, ?, ?)
    """,
    travellers,
)

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    name                        TEXT NOT NULL,
    email                       TEXT NOT NULL UNIQUE,
    password_hash               TEXT NOT NULL,
    is_validated                INTEGER NOT NULL DEFAULT 0,
    verification_token          TEXT,
    verification_expires_at     TEXT,
    last_verification_sent_at   TEXT,
    verification_resend_count   INTEGER NOT NULL DEFAULT 0,
    verification_blocked_until  TEXT,
    created_at                  TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS access_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    sign_in_at  TEXT NOT NULL,
    sign_out_at TEXT,
    in_session  INTEGER NOT NULL DEFAULT 0
)
""")

cursor.execute("DELETE FROM access_logs")
cursor.execute("DELETE FROM users")

now = datetime.now(timezone.utc)
seed_password_hash = generate_password_hash("Placeholder1!")

users = [
    (
        i,
        f"Traveller {i}",
        f"traveller{i}@example.com",
        seed_password_hash,
        1 if i % 2 == 0 else 0,
        (now - timedelta(days=30 - i)).isoformat(timespec="seconds"),
    )
    for i in range(1, 11)
]

cursor.executemany(
    """
    INSERT INTO users (id, name, email, password_hash, is_validated, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    users,
)

access_logs = []
for i in range(1, 11):
    signed_out = i % 3 != 0
    sign_in_at = (now - timedelta(days=30 - i, hours=1)).isoformat(timespec="seconds")
    sign_out_at = (
        (now - timedelta(days=30 - i, minutes=30)).isoformat(timespec="seconds")
        if signed_out
        else None
    )
    access_logs.append((i, i, sign_in_at, sign_out_at, 0 if signed_out else 1))

cursor.executemany(
    """
    INSERT INTO access_logs (id, user_id, sign_in_at, sign_out_at, in_session)
    VALUES (?, ?, ?, ?, ?)
    """,
    access_logs,
)

conn.commit()
conn.close()

print(
    f"shared-db initialised with {len(travellers)} travellers, "
    f"{len(users)} users and {len(access_logs)} access log entries."
)
