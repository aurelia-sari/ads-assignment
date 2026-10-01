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

# Clear existing seed data - this is a full replace, not an incremental add
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
# Seed budgets - 12
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
# Seed flights - round trips for 5 Australian cities and 5 Japan
# cities, all via Sydney. Each destination has 2 outbound options
# and 2 return options (different airline/time/price), so search
# results have more than one option to rank.
# ---------------------------------------------------------
flights = [

    # --- Melbourne ---
    ("Qantas", "QF409", "Sydney", "Melbourne", "2026-09-10", "07:00", "08:30", 90, 0, 189, 95, 4.7, now),
    ("Virgin Australia", "VA410", "Sydney", "Melbourne", "2026-09-10", "14:00", "15:30", 90, 0, 165, 88, 4.3, now),
    ("Qantas", "QF410", "Melbourne", "Sydney", "2026-09-17", "09:00", "10:30", 90, 0, 195, 95, 4.7, now),
    ("Virgin Australia", "VA411", "Melbourne", "Sydney", "2026-09-17", "16:00", "17:30", 90, 0, 170, 88, 4.3, now),

    # --- Brisbane ---
    ("Virgin Australia", "VA863", "Sydney", "Brisbane", "2026-09-10", "09:15", "10:35", 80, 0, 175, 93, 4.6, now),
    ("Jetstar", "JQ700", "Sydney", "Brisbane", "2026-09-10", "18:00", "19:20", 80, 0, 145, 85, 4.1, now),
    ("Virgin Australia", "VA864", "Brisbane", "Sydney", "2026-09-17", "11:00", "12:20", 80, 0, 180, 93, 4.6, now),
    ("Jetstar", "JQ701", "Brisbane", "Sydney", "2026-09-17", "19:30", "20:50", 80, 0, 150, 85, 4.1, now),

    # --- Perth ---
    ("Jetstar", "JQ501", "Sydney", "Perth", "2026-09-11", "06:30", "11:30", 300, 0, 459, 89, 4.2, now),
    ("Qantas", "QF577", "Sydney", "Perth", "2026-09-11", "13:00", "18:00", 300, 0, 510, 92, 4.5, now),
    ("Jetstar", "JQ502", "Perth", "Sydney", "2026-09-18", "12:30", "17:35", 305, 0, 465, 89, 4.2, now),
    ("Qantas", "QF578", "Perth", "Sydney", "2026-09-18", "19:30", "00:35", 305, 0, 520, 92, 4.5, now),

    # --- Adelaide ---
    ("Qantas", "QF737", "Sydney", "Adelaide", "2026-09-12", "14:00", "16:00", 120, 0, 210, 90, 4.5, now),
    ("Virgin Australia", "VA720", "Sydney", "Adelaide", "2026-09-12", "08:00", "10:00", 120, 0, 195, 86, 4.2, now),
    ("Qantas", "QF738", "Adelaide", "Sydney", "2026-09-19", "16:30", "18:30", 120, 0, 215, 90, 4.5, now),
    ("Virgin Australia", "VA721", "Adelaide", "Sydney", "2026-09-19", "10:30", "12:30", 120, 0, 200, 86, 4.2, now),

    # --- Gold Coast ---
    ("Virgin Australia", "VA936", "Sydney", "Gold Coast", "2026-09-12", "08:00", "09:25", 85, 0, 165, 92, 4.5, now),
    ("Jetstar", "JQ764", "Sydney", "Gold Coast", "2026-09-12", "15:30", "16:55", 85, 0, 145, 86, 4.2, now),
    ("Virgin Australia", "VA937", "Gold Coast", "Sydney", "2026-09-19", "10:00", "11:25", 85, 0, 170, 92, 4.5, now),
    ("Jetstar", "JQ765", "Gold Coast", "Sydney", "2026-09-19", "17:30", "18:55", 85, 0, 150, 86, 4.2, now),

    # --- Tokyo ---
    ("Qantas", "QF25", "Sydney", "Tokyo", "2026-10-12", "09:20", "18:50", 570, 0, 950, 90, 4.6, now),
    ("Japan Airlines", "JL771", "Sydney", "Tokyo", "2026-10-12", "19:30", "05:00", 570, 0, 880, 86, 4.4, now),
    ("Qantas", "QF26", "Tokyo", "Sydney", "2026-10-19", "21:30", "09:30", 570, 0, 950, 90, 4.6, now),
    ("Japan Airlines", "JL770", "Tokyo", "Sydney", "2026-10-19", "11:00", "21:30", 570, 0, 870, 86, 4.4, now),

    # --- Osaka ---
    ("Japan Airlines", "JL772", "Sydney", "Osaka", "2026-10-12", "11:00", "19:30", 510, 0, 890, 87, 4.5, now),
    ("ANA", "NH878", "Sydney", "Osaka", "2026-10-12", "20:00", "04:30", 510, 0, 860, 83, 4.3, now),
    ("Japan Airlines", "JL773", "Osaka", "Sydney", "2026-10-19", "21:00", "07:30", 510, 0, 890, 87, 4.5, now),
    ("ANA", "NH877", "Osaka", "Sydney", "2026-10-19", "09:00", "17:30", 510, 0, 855, 83, 4.3, now),

    # --- Nagoya ---
    ("ANA", "NH879", "Sydney", "Nagoya", "2026-10-13", "10:15", "19:00", 525, 0, 910, 85, 4.4, now),
    ("Japan Airlines", "JL855", "Sydney", "Nagoya", "2026-10-13", "20:30", "05:15", 525, 0, 875, 80, 4.1, now),
    ("ANA", "NH880", "Nagoya", "Sydney", "2026-10-20", "20:30", "07:00", 525, 0, 910, 85, 4.4, now),
    ("Japan Airlines", "JL856", "Nagoya", "Sydney", "2026-10-20", "08:30", "17:15", 525, 0, 880, 80, 4.1, now),

    # --- Fukuoka ---
    ("Japan Airlines", "JL881", "Sydney", "Fukuoka", "2026-10-13", "08:40", "17:10", 510, 0, 870, 84, 4.3, now),
    ("ANA", "NH655", "Sydney", "Fukuoka", "2026-10-13", "21:00", "05:30", 510, 0, 840, 79, 4.0, now),
    ("Japan Airlines", "JL882", "Fukuoka", "Sydney", "2026-10-20", "19:00", "05:30", 510, 0, 870, 84, 4.3, now),
    ("ANA", "NH656", "Fukuoka", "Sydney", "2026-10-20", "07:30", "16:00", 510, 1, 845, 79, 4.0, now),

    # --- Sapporo ---
    ("ANA", "NH956", "Sydney", "Sapporo", "2026-10-14", "09:00", "19:30", 630, 1, 990, 82, 4.2, now),
    ("Japan Airlines", "JL507", "Sydney", "Sapporo", "2026-10-14", "21:30", "08:00", 630, 1, 960, 78, 4.0, now),
    ("ANA", "NH957", "Sapporo", "Sydney", "2026-10-21", "19:30", "08:00", 630, 1, 990, 82, 4.2, now),
    ("Japan Airlines", "JL508", "Sapporo", "Sydney", "2026-10-21", "09:30", "20:00", 630, 1, 965, 78, 4.0, now),

]

cursor.executemany("""
INSERT INTO flights
(airline, flight_number, origin, destination, departure_date,
 departure_time, arrival_time, duration_minutes, stops, price_aud,
 popularity_score, rating, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", flights)

# ---------------------------------------------------------
# Seed hotels - 2 in Sydney (home base) plus 2 each in the 5
# Australian and 5 Japan destinations above (22 total).
# ---------------------------------------------------------
hotels = [

    # --- Sydney (home base) ---
    ("Sydney Harbour Hotel", "Sydney", "2026-09-10", "2026-09-13", 1, 220, 660, 4.7, 95, now),
    ("Central Sydney Suites", "Sydney", "2026-09-10", "2026-09-13", 1, 180, 540, 4.4, 90, now),

    # --- Melbourne ---
    ("Melbourne CBD Hotel", "Melbourne", "2026-09-10", "2026-09-17", 1, 195, 1365, 4.6, 93, now),
    ("Southbank Melbourne Suites", "Melbourne", "2026-09-10", "2026-09-17", 1, 150, 1050, 4.2, 87, now),

    # --- Brisbane ---
    ("Brisbane River Hotel", "Brisbane", "2026-09-10", "2026-09-17", 1, 175, 1225, 4.5, 90, now),
    ("Brisbane Riverside Inn", "Brisbane", "2026-09-10", "2026-09-17", 1, 140, 980, 4.1, 82, now),

    # --- Perth ---
    ("Perth City Central", "Perth", "2026-09-11", "2026-09-18", 1, 190, 1330, 4.6, 91, now),
    ("Perth Swan River Lodge", "Perth", "2026-09-11", "2026-09-18", 1, 160, 1120, 4.2, 84, now),

    # --- Adelaide ---
    ("Adelaide Central Hotel", "Adelaide", "2026-09-12", "2026-09-19", 1, 160, 1120, 4.3, 85, now),
    ("Adelaide Hills Boutique Hotel", "Adelaide", "2026-09-12", "2026-09-19", 1, 145, 1015, 4.1, 80, now),

    # --- Gold Coast ---
    ("Gold Coast Beachfront Resort", "Gold Coast", "2026-09-12", "2026-09-19", 1, 210, 1470, 4.7, 94, now),
    ("Gold Coast Surfers Paradise Inn", "Gold Coast", "2026-09-12", "2026-09-19", 1, 175, 1225, 4.3, 86, now),

    # --- Tokyo ---
    ("Tokyo Shinjuku Hotel", "Tokyo", "2026-10-12", "2026-10-19", 1, 250, 1750, 4.6, 92, now),
    ("Tokyo Asakusa Ryokan", "Tokyo", "2026-10-12", "2026-10-19", 1, 210, 1470, 4.4, 85, now),

    # --- Osaka ---
    ("Osaka Namba Hotel", "Osaka", "2026-10-12", "2026-10-19", 1, 210, 1470, 4.4, 88, now),
    ("Osaka Umeda Tower Hotel", "Osaka", "2026-10-12", "2026-10-19", 1, 230, 1610, 4.5, 86, now),

    # --- Nagoya ---
    ("Nagoya Central Hotel", "Nagoya", "2026-10-13", "2026-10-20", 1, 190, 1330, 4.3, 84, now),
    ("Nagoya Sakae Suites", "Nagoya", "2026-10-13", "2026-10-20", 1, 170, 1190, 4.1, 79, now),

    # --- Fukuoka ---
    ("Fukuoka Tenjin Hotel", "Fukuoka", "2026-10-13", "2026-10-20", 1, 180, 1260, 4.2, 82, now),
    ("Fukuoka Hakata Station Hotel", "Fukuoka", "2026-10-13", "2026-10-20", 1, 165, 1155, 4.0, 77, now),

    # --- Sapporo ---
    ("Sapporo Susukino Hotel", "Sapporo", "2026-10-14", "2026-10-21", 1, 200, 1400, 4.3, 80, now),
    ("Sapporo Odori Park Hotel", "Sapporo", "2026-10-14", "2026-10-21", 1, 185, 1295, 4.1, 76, now),

]

cursor.executemany("""
INSERT INTO hotels
(name, destination, check_in, check_out, rooms,
 price_per_night_aud, total_price_aud, rating,
 popularity_score, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", hotels)

# ---------------------------------------------------------
# Seed trip selections - 12
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
# Seed search history - 12, cycling through all 10 destinations
# (5 Australian, 5 Japan) for variety.
# ---------------------------------------------------------
history = []

destinations_cycle = [
    "Melbourne", "Tokyo", "Brisbane", "Osaka", "Perth",
    "Nagoya", "Adelaide", "Fukuoka", "Gold Coast", "Sapporo",
]

for i in range(1, 13):
    history.append(
        (
            i,
            "flight" if i % 2 else "hotel",
            "Sydney",
            destinations_cycle[i % len(destinations_cycle)],
            "2026-09-10",
            "2026-09-17",
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
print("Flights: round trips (2 options each way) for 5 AU cities and 5 Japan cities via Sydney.")
print("Hotels: 2 in Sydney plus 2 each in all 10 destination cities.")