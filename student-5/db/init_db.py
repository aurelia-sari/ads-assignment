"""Student 5 - Aung Ko Khaing
Bookings & Budget database initialisation.

The database is owned by student-5-db.
The API service must communicate with this database only through
the student-5-db HTTP API.
"""

import os
import sqlite3
from datetime import date, timedelta

# FIX: was hardcoded to "/app/data", an absolute path that only exists
# inside the Docker container. Running this script directly with
# `python3 init_db.py` on a local machine tried to create a folder at
# the filesystem root (/app) and failed with PermissionError. Basing
# the path on this script's own location works both inside Docker
# (WORKDIR /app -> resolves to /app/data, unchanged) and locally
# (resolves to a "data" folder next to this file).
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
# Seed flights - 12
# ---------------------------------------------------------
flights = [
    (
        "Qantas",
        "QF1",
        "Sydney",
        "London",
        "2026-09-10",
        "16:00",
        "06:30",
        1320,
        1,
        1850,
        95,
        4.8,
        now,
    ),
    (
        "Singapore Airlines",
        "SQ222",
        "Sydney",
        "Singapore",
        "2026-09-10",
        "18:00",
        "00:30",
        500,
        0,
        720,
        96,
        4.9,
        now,
    ),
    (
        "Emirates",
        "EK413",
        "Sydney",
        "Dubai",
        "2026-09-11",
        "21:45",
        "05:45",
        870,
        0,
        1100,
        94,
        4.8,
        now,
    ),
    (
        "Qantas",
        "QF127",
        "Sydney",
        "Hong Kong",
        "2026-09-12",
        "10:00",
        "18:00",
        540,
        0,
        850,
        91,
        4.7,
        now,
    ),
    (
        "Cathay Pacific",
        "CX100",
        "Sydney",
        "Hong Kong",
        "2026-09-12",
        "14:30",
        "22:20",
        530,
        0,
        790,
        90,
        4.7,
        now,
    ),
    (
        "Jetstar",
        "JQ35",
        "Sydney",
        "Tokyo",
        "2026-09-15",
        "09:00",
        "18:00",
        600,
        0,
        580,
        82,
        4.2,
        now,
    ),
    (
        "ANA",
        "NH880",
        "Sydney",
        "Tokyo",
        "2026-09-15",
        "21:00",
        "06:00",
        600,
        0,
        1050,
        93,
        4.9,
        now,
    ),
    (
        "Virgin Australia",
        "VA1",
        "Sydney",
        "Los Angeles",
        "2026-09-18",
        "11:00",
        "06:30",
        870,
        0,
        1250,
        87,
        4.4,
        now,
    ),
    (
        "United Airlines",
        "UA842",
        "Sydney",
        "Los Angeles",
        "2026-09-18",
        "14:00",
        "09:00",
        900,
        0,
        1190,
        88,
        4.5,
        now,
    ),
    (
        "Thai Airways",
        "TG476",
        "Sydney",
        "Bangkok",
        "2026-09-20",
        "10:30",
        "16:45",
        555,
        0,
        680,
        89,
        4.6,
        now,
    ),
    (
        "Malaysia Airlines",
        "MH122",
        "Sydney",
        "Kuala Lumpur",
        "2026-09-22",
        "13:00",
        "19:00",
        480,
        0,
        620,
        86,
        4.4,
        now,
    ),
    (
        "Air New Zealand",
        "NZ102",
        "Sydney",
        "Auckland",
        "2026-09-25",
        "08:00",
        "13:20",
        200,
        0,
        450,
        84,
        4.3,
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
# Seed hotels - 12
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
        "Tokyo Grand Hotel",
        "Tokyo",
        "2026-09-15",
        "2026-09-20",
        1,
        210,
        1050,
        4.8,
        96,
        now,
    ),
    (
        "Tokyo City Inn",
        "Tokyo",
        "2026-09-15",
        "2026-09-20",
        1,
        130,
        650,
        4.2,
        85,
        now,
    ),
    (
        "Bangkok Riverside",
        "Bangkok",
        "2026-09-20",
        "2026-09-25",
        1,
        120,
        600,
        4.5,
        92,
        now,
    ),
    (
        "Bangkok Budget Hotel",
        "Bangkok",
        "2026-09-20",
        "2026-09-25",
        1,
        75,
        375,
        4.1,
        82,
        now,
    ),
    (
        "Hong Kong Central",
        "Hong Kong",
        "2026-09-12",
        "2026-09-16",
        1,
        190,
        760,
        4.6,
        91,
        now,
    ),
    (
        "Kowloon Harbour View",
        "Hong Kong",
        "2026-09-12",
        "2026-09-16",
        1,
        150,
        600,
        4.3,
        87,
        now,
    ),
    (
        "London Central Hotel",
        "London",
        "2026-09-10",
        "2026-09-15",
        1,
        260,
        1300,
        4.8,
        94,
        now,
    ),
    (
        "London Budget Stay",
        "London",
        "2026-09-10",
        "2026-09-15",
        1,
        170,
        850,
        4.1,
        80,
        now,
    ),
    (
        "LA Downtown Hotel",
        "Los Angeles",
        "2026-09-18",
        "2026-09-23",
        1,
        200,
        1000,
        4.5,
        89,
        now,
    ),
    (
        "Auckland Harbour Lodge",
        "Auckland",
        "2026-09-25",
        "2026-09-29",
        1,
        160,
        640,
        4.4,
        86,
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
# Seed search history - 10+
# ---------------------------------------------------------
history = []

for i in range(1, 13):
    history.append(
        (
            i,
            "flight" if i % 2 else "hotel",
            "Sydney",
            ["Tokyo", "Bangkok", "London", "Hong Kong"][i % 4],
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