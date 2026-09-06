"""Student 5 - Aung Ko Khaing
Bookings & Budget database initialisation.

The database is owned by student-5-db.
The API service must communicate with this database only through
the student-5-db HTTP API.
"""

import os
import sqlite3
from datetime import date, timedelta


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATABASE_NAME = os.path.join(DATA_DIR, "student5.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

# ---------------------------------------------------------
# Budgets
# ---------------------------------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS budgets (
    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    total_budget REAL NOT NULL,
    flight_budget REAL NOT NULL DEFAULT 0,
    hotel_budget REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'AUD',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
""")

# ---------------------------------------------------------
# Flights
# ---------------------------------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS flights (
    flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    airline TEXT NOT NULL,
    flight_number TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_date TEXT NOT NULL,
    departure_time TEXT NOT NULL,
    arrival_time TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    stops INTEGER NOT NULL DEFAULT 0,
    price_aud REAL NOT NULL,
    popularity_score REAL NOT NULL DEFAULT 0,
    rating REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
""")

# ---------------------------------------------------------
# Hotels
# ---------------------------------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS hotels (
    hotel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    destination TEXT NOT NULL,
    check_in TEXT NOT NULL,
    check_out TEXT NOT NULL,
    rooms INTEGER NOT NULL DEFAULT 1,
    price_per_night_aud REAL NOT NULL,
    total_price_aud REAL NOT NULL,
    rating REAL NOT NULL DEFAULT 0,
    popularity_score REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
""")

# ---------------------------------------------------------
# Trip selections
# ---------------------------------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS trip_selections (
    selection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    item_type TEXT NOT NULL CHECK(item_type IN ('flight', 'hotel')),
    item_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    price_aud REAL NOT NULL,
    selected_at TEXT NOT NULL
)
""")

# ---------------------------------------------------------
# Search history
# ---------------------------------------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS search_history (
    search_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER,
    search_type TEXT NOT NULL,
    origin TEXT,
    destination TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    travellers INTEGER NOT NULL DEFAULT 1,
    budget_aud REAL,
    search_query TEXT,
    created_at TEXT NOT NULL
)
""")

# Clear existing seed data
for table in [
    "budgets",
    "flights",
    "hotels",
    "trip_selections",
    "search_history",
]:
    cursor.execute(f"DELETE FROM {table}")

now = "2026-08-31T00:00:00"

# ---------------------------------------------------------
# Seed budgets - 10+
# ---------------------------------------------------------
budgets = []

for i in range(1, 13):
    total = 1000 + (i * 500)
    budgets.append(
        (
            i,
            total,
            total * 0.45,
            total * 0.40,
            "AUD",
            now,
            now,
        )
    )

cursor.executemany("""
INSERT INTO budgets
(trip_id, total_budget, flight_budget, hotel_budget, currency,
 created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", budgets)

# ---------------------------------------------------------
# Seed flights - 12 domestic Australian routes, all from Sydney
# ---------------------------------------------------------
flights = [
    (
        "Qantas",
        "QF409",
        "Sydney",
        "Melbourne",
        "2026-09-10",
        "07:00",
        "08:30",
        90,
        0,
        189,
        95,
        4.7,
        now,
    ),
    (
        "Virgin Australia",
        "VA863",
        "Sydney",
        "Brisbane",
        "2026-09-10",
        "09:15",
        "10:35",
        80,
        0,
        175,
        93,
        4.6,
        now,
    ),
    (
        "Jetstar",
        "JQ501",
        "Sydney",
        "Perth",
        "2026-09-11",
        "06:30",
        "11:30",
        300,
        0,
        459,
        89,
        4.2,
        now,
    ),
    (
        "Qantas",
        "QF737",
        "Sydney",
        "Adelaide",
        "2026-09-12",
        "14:00",
        "16:00",
        120,
        0,
        210,
        90,
        4.5,
        now,
    ),
    (
        "Virgin Australia",
        "VA936",
        "Sydney",
        "Gold Coast",
        "2026-09-12",
        "08:00",
        "09:25",
        85,
        0,
        165,
        92,
        4.5,
        now,
    ),
    (
        "Jetstar",
        "JQ905",
        "Sydney",
        "Cairns",
        "2026-09-15",
        "10:00",
        "12:55",
        175,
        0,
        320,
        88,
        4.3,
        now,
    ),
    (
        "Qantas",
        "QF1400",
        "Sydney",
        "Canberra",
        "2026-09-15",
        "17:00",
        "17:55",
        55,
        0,
        145,
        85,
        4.4,
        now,
    ),
    (
        "Virgin Australia",
        "VA1257",
        "Sydney",
        "Hobart",
        "2026-09-18",
        "07:45",
        "09:55",
        130,
        0,
        225,
        89,
        4.6,
        now,
    ),
    (
        "Qantas",
        "QF825",
        "Sydney",
        "Darwin",
        "2026-09-18",
        "12:00",
        "16:35",
        275,
        0,
        410,
        87,
        4.5,
        now,
    ),
    (
        "Jetstar",
        "JQ764",
        "Sydney",
        "Sunshine Coast",
        "2026-09-20",
        "15:30",
        "16:55",
        85,
        0,
        170,
        86,
        4.2,
        now,
    ),
    (
        "Rex Airlines",
        "ZL231",
        "Sydney",
        "Launceston",
        "2026-09-22",
        "09:00",
        "11:10",
        130,
        0,
        235,
        84,
        4.3,
        now,
    ),
    (
        "Qantas",
        "QF841",
        "Sydney",
        "Alice Springs",
        "2026-09-25",
        "11:00",
        "14:20",
        200,
        0,
        340,
        91,
        4.6,
        now,
    ),
]

cursor.executemany("""
INSERT INTO flights
(airline, flight_number, origin, destination, departure_date,
 departure_time, arrival_time, duration_minutes, stops, price_aud,
 popularity_score, rating, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", flights)

# ---------------------------------------------------------
# Seed hotels - 12, across the same Australian destinations
# ---------------------------------------------------------
hotels = [
    (
        "Sydney Harbour Hotel",
        "Sydney",
        "2026-09-10",
        "2026-09-13",
        1,
        220,
        660,
        4.7,
        95,
        now,
    ),
    (
        "Central Sydney Suites",
        "Sydney",
        "2026-09-10",
        "2026-09-13",
        1,
        180,
        540,
        4.4,
        90,
        now,
    ),
    (
        "Melbourne CBD Hotel",
        "Melbourne",
        "2026-09-10",
        "2026-09-13",
        1,
        195,
        585,
        4.6,
        93,
        now,
    ),
    (
        "Southbank Melbourne Suites",
        "Melbourne",
        "2026-09-10",
        "2026-09-13",
        1,
        150,
        450,
        4.2,
        87,
        now,
    ),
    (
        "Brisbane River Hotel",
        "Brisbane",
        "2026-09-12",
        "2026-09-15",
        1,
        175,
        525,
        4.5,
        90,
        now,
    ),
    (
        "Perth City Central",
        "Perth",
        "2026-09-11",
        "2026-09-16",
        1,
        190,
        950,
        4.6,
        91,
        now,
    ),
    (
        "Adelaide Central Hotel",
        "Adelaide",
        "2026-09-12",
        "2026-09-16",
        1,
        160,
        640,
        4.3,
        85,
        now,
    ),
    (
        "Gold Coast Beachfront Resort",
        "Gold Coast",
        "2026-09-12",
        "2026-09-17",
        1,
        210,
        1050,
        4.7,
        94,
        now,
    ),
    (
        "Cairns Esplanade Hotel",
        "Cairns",
        "2026-09-15",
        "2026-09-20",
        1,
        200,
        1000,
        4.5,
        90,
        now,
    ),
    (
        "Hobart Waterfront Inn",
        "Hobart",
        "2026-09-18",
        "2026-09-22",
        1,
        165,
        660,
        4.4,
        86,
        now,
    ),
    (
        "Darwin Harbourview Hotel",
        "Darwin",
        "2026-09-18",
        "2026-09-23",
        1,
        185,
        925,
        4.3,
        84,
        now,
    ),
    (
        "Alice Springs Desert Lodge",
        "Alice Springs",
        "2026-09-25",
        "2026-09-29",
        1,
        155,
        620,
        4.2,
        82,
        now,
    ),
]

cursor.executemany("""
INSERT INTO hotels
(name, destination, check_in, check_out, rooms,
 price_per_night_aud, total_price_aud, rating,
 popularity_score, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", hotels)

# ---------------------------------------------------------
# Seed trip selections - 10+
# ---------------------------------------------------------
selections = []

for i in range(1, 13):
    selections.append(
        (
            i,
            "flight" if i % 2 else "hotel",
            i,
            f"Sample selected item {i}",
            300 + (i * 50),
            now,
        )
    )

cursor.executemany("""
INSERT INTO trip_selections
(trip_id, item_type, item_id, item_name, price_aud, selected_at)
VALUES (?, ?, ?, ?, ?, ?)
""", selections)

# ---------------------------------------------------------
# Seed search history - 10+, Australian destinations
# ---------------------------------------------------------
history = []

for i in range(1, 13):
    history.append(
        (
            i,
            "flight" if i % 2 else "hotel",
            "Sydney",
            ["Melbourne", "Brisbane", "Perth", "Cairns"][i % 4],
            "2026-09-10",
            "2026-09-15",
            1 + (i % 3),
            500 + i * 200,
            f"Sample search {i}",
            now,
        )
    )

cursor.executemany("""
INSERT INTO search_history
(trip_id, search_type, origin, destination,
 start_date, end_date, travellers, budget_aud,
 search_query, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", history)

conn.commit()
conn.close()

print("student-5-db initialised successfully.")
print("Tables: budgets, flights, hotels, trip_selections, search_history")
print("Each table contains at least 10 seed records.")