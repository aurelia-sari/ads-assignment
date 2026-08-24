"""Create and seed the Trips & Itinerary database.

Owned by student-1. Two tables, each seeded with more than the ten records the
project specification requires.
"""

import os
import sqlite3

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "trips.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS trips (
    trip_id        INTEGER PRIMARY KEY,
    trip_name      TEXT NOT NULL,
    destination    TEXT NOT NULL,
    start_date     TEXT NOT NULL,
    end_date       TEXT NOT NULL,
    traveller_id   INTEGER NOT NULL,
    budget_aud     REAL NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'planned'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS itinerary_days (
    day_id      INTEGER PRIMARY KEY,
    trip_id     INTEGER NOT NULL,
    day_number  INTEGER NOT NULL,
    day_date    TEXT NOT NULL,
    location    TEXT NOT NULL,
    activity    TEXT NOT NULL,
    notes       TEXT DEFAULT '',
    FOREIGN KEY (trip_id) REFERENCES trips (trip_id) ON DELETE CASCADE
)
""")

cursor.execute("DELETE FROM itinerary_days")
cursor.execute("DELETE FROM trips")

trips = [
    (1,  "Golden Week in Kyoto",     "Kyoto, Japan",          "2026-04-25", "2026-05-03", 1,  4200.00, "booked"),
    (2,  "Amalfi Coast Road Trip",   "Amalfi, Italy",         "2026-06-10", "2026-06-20", 2,  6800.00, "planned"),
    (3,  "Patagonia Trekking",       "El Chalten, Argentina", "2026-11-02", "2026-11-16", 3,  9100.00, "planned"),
    (4,  "Vietnam Street Food Tour", "Hanoi, Vietnam",        "2026-03-08", "2026-03-18", 4,  3300.00, "completed"),
    (5,  "Iceland Ring Road",        "Reykjavik, Iceland",    "2026-08-01", "2026-08-12", 5,  8750.00, "booked"),
    (6,  "Queenstown Ski Week",      "Queenstown, NZ",        "2026-07-04", "2026-07-11", 6,  3950.00, "booked"),
    (7,  "Marrakech and the Atlas",  "Marrakech, Morocco",    "2026-10-14", "2026-10-24", 7,  5200.00, "planned"),
    (8,  "Lisbon City Break",        "Lisbon, Portugal",      "2026-05-16", "2026-05-22", 8,  2900.00, "cancelled"),
    (9,  "Great Barrier Reef Dive",  "Cairns, Australia",     "2026-09-05", "2026-09-12", 9,  3100.00, "planned"),
    (10, "Seoul and Jeju",           "Seoul, South Korea",    "2026-04-02", "2026-04-13", 10, 5600.00, "completed"),
    (11, "Norwegian Fjords",         "Bergen, Norway",        "2026-06-27", "2026-07-06", 11, 7400.00, "planned"),
    (12, "Sri Lanka Tea Country",    "Kandy, Sri Lanka",      "2026-02-12", "2026-02-23", 12, 3850.00, "completed"),
]

cursor.executemany(
    """
    INSERT INTO trips (trip_id, trip_name, destination, start_date, end_date,
                       traveller_id, budget_aud, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    trips,
)

itinerary_days = [
    (1,  1, 1, "2026-04-25", "Kyoto",        "Arrive, Gion evening walk",        "Drop bags at ryokan first"),
    (2,  1, 2, "2026-04-26", "Kyoto",        "Fushimi Inari at sunrise",         "Beat the crowds, go before 7am"),
    (3,  1, 3, "2026-04-27", "Arashiyama",   "Bamboo grove and monkey park",     "Half day, train from Kyoto"),
    (4,  1, 4, "2026-04-28", "Nara",         "Todai-ji and deer park day trip",  "45 min by local line"),
    (5,  2, 1, "2026-06-10", "Naples",       "Collect hire car, drive to Amalfi","Book ZTL permit in advance"),
    (6,  2, 2, "2026-06-11", "Positano",     "Beach day and cliff path",         "Parking is scarce after 9am"),
    (7,  2, 3, "2026-06-12", "Ravello",      "Villa Rufolo gardens and concert", "Tickets sell out"),
    (8,  3, 1, "2026-11-02", "El Chalten",   "Arrive, gear check, short hike",   "Altitude is mild here"),
    (9,  3, 2, "2026-11-03", "Laguna de los Tres", "Full day trek",              "10 hours return, pack lunch"),
    (10, 4, 1, "2026-03-08", "Hanoi",        "Old Quarter food walk",            "Cash only at most stalls"),
    (11, 4, 2, "2026-03-09", "Hanoi",        "Cooking class and market tour",    "Booked for 9am"),
    (12, 5, 1, "2026-08-01", "Reykjavik",    "Arrive, collect campervan",        "Check tyre and weather advice"),
    (13, 5, 2, "2026-08-02", "Golden Circle","Thingvellir, Geysir, Gullfoss",    "Long driving day"),
    (14, 6, 1, "2026-07-04", "Queenstown",   "Arrive, collect ski hire",         "Shop closes 6pm"),
    (15, 9, 1, "2026-09-05", "Cairns",       "Arrive, dive medical check",       "Required before liveaboard"),
]

cursor.executemany(
    """
    INSERT INTO itinerary_days (day_id, trip_id, day_number, day_date,
                                location, activity, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    itinerary_days,
)

conn.commit()
conn.close()

print(
    f"student-1-db initialised with {len(trips)} trips "
    f"and {len(itinerary_days)} itinerary days."
)
