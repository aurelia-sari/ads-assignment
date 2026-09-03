"""Create the Account & Dashboard database (student-4, Aurelia Sari).

User accounts and access logs live in shared-db (see shared/db/init_db.py)
since a user's id and sign-in state are shared data every feature may need.

This database owns the Travel Guides destinations: the cities a guide can be
looked up for. The seed list mirrors the Australian cities already used as
flight and hotel destinations in student-5 (Bookings & Budget).
"""

import os
import sqlite3

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "student4.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS destinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    region TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS currency_infos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id INTEGER NOT NULL REFERENCES destinations(id),
    currency_code TEXT NOT NULL,
    currency_name TEXT NOT NULL,
    exchange_tips TEXT NOT NULL
)
""")

cursor.execute("DELETE FROM currency_infos")
cursor.execute("DELETE FROM destinations")

destinations = [
    ("Australia", "Sydney", "New South Wales"),
    ("Australia", "Melbourne", "Victoria"),
    ("Australia", "Brisbane", "Queensland"),
    ("Australia", "Perth", "Western Australia"),
    ("Australia", "Adelaide", "South Australia"),
    ("Australia", "Gold Coast", "Queensland"),
    ("Australia", "Cairns", "Queensland"),
    ("Australia", "Canberra", "Australian Capital Territory"),
    ("Australia", "Hobart", "Tasmania"),
    ("Australia", "Darwin", "Northern Territory"),
    ("Australia", "Sunshine Coast", "Queensland"),
    ("Australia", "Launceston", "Tasmania"),
    ("Australia", "Alice Springs", "Northern Territory"),
]

cursor.executemany(
    "INSERT INTO destinations (country, city, region) VALUES (?, ?, ?)",
    destinations,
)

# Every seeded destination is in Australia, so they all share one currency.
destination_ids = [row[0] for row in cursor.execute("SELECT id FROM destinations")]

currency_infos = [
    (
        destination_id,
        "AUD",
        "Australian Dollar",
        "Cards are accepted almost everywhere. Carry a little cash for small "
        "regional towns and markets. One AUD equals 100 cents.",
    )
    for destination_id in destination_ids
]

cursor.executemany(
    "INSERT INTO currency_infos (destination_id, currency_code, currency_name, exchange_tips) "
    "VALUES (?, ?, ?, ?)",
    currency_infos,
)

conn.commit()
conn.close()

print("student-4-db initialised.")
print(f"Tables: destinations ({len(destinations)} seed records), "
      f"currency_infos ({len(currency_infos)} seed records).")
