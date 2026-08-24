"""Create and seed the shared access database.

The shared database owns only cross-cutting access data: the traveller
accounts every feature needs to resolve a traveller_id. Feature data lives in
each student's own database microservice.
"""

import os
import sqlite3

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

conn.commit()
conn.close()

print(f"shared-db initialised with {len(travellers)} travellers.")
