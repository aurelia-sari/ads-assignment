"""Student 5 - Aung Ko Khaing
Bookings & Budget database initialisation.

The database is owned by student-5-db.
The API service must communicate with this database only through
the student-5-db HTTP API.
"""

import os
import sqlite3


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
for table in ["budgets", "flights", "hotels", "trip_selections", "search_history"]:
    cursor.execute(f"DELETE FROM {table}")

now = "2026-09-30T00:00:00"

# ---------------------------------------------------------
# Destinations: 5 Australian cities + 5 Japan cities, all via Sydney
# ---------------------------------------------------------
DESTINATIONS = [
    # (city, country, airline, out_flight_no, ret_flight_no, out_price, ret_price,
    #  out_date, ret_date, out_dep, out_arr, ret_dep, ret_arr, duration_min)
    ("Melbourne",  "Australia", "Qantas",           "QF409", "QF412", 189, 199, "2026-11-10", "2026-11-17", "07:00", "08:30", "18:10", "19:40", 90),
    ("Brisbane",   "Australia", "Virgin Australia",  "VA863", "VA870", 175, 185, "2026-11-10", "2026-11-17", "09:15", "10:35", "16:45", "18:05", 80),
    ("Perth",      "Australia", "Jetstar",           "JQ501", "JQ508", 459, 479, "2026-11-11", "2026-11-18", "06:30", "11:30", "12:30", "14:05", 300),
    ("Adelaide",   "Australia", "Qantas",            "QF737", "QF744", 210, 225, "2026-11-12", "2026-11-19", "14:00", "16:00", "17:30", "19:35", 120),
    ("Gold Coast", "Australia", "Virgin Australia",  "VA936", "VA941", 165, 175, "2026-11-12", "2026-11-19", "08:00", "09:25", "15:20", "16:50", 85),
    ("Tokyo",      "Japan",     "Japan Airlines",    "JL51",  "JL52",  890, 920, "2026-11-13", "2026-11-22", "11:10", "19:05", "21:30", "06:10", 590),
    ("Osaka",      "Japan",     "Qantas",            "QF25",  "QF26",  845, 870, "2026-11-13", "2026-11-22", "12:40", "20:15", "22:00", "07:20", 575),
    ("Nagoya",     "Japan",     "ANA",               "NH879", "NH880", 920, 950, "2026-11-14", "2026-11-23", "10:25", "18:30", "20:10", "05:05", 605),
    ("Fukuoka",    "Japan",     "Jetstar",           "JQ81",  "JQ82",  760, 790, "2026-11-14", "2026-11-23", "13:15", "21:40", "23:00", "08:35", 625),
    ("Sapporo",    "Japan",     "ANA",               "NH895", "NH896", 980, 1010, "2026-11-15", "2026-11-24", "09:50", "18:45", "19:50", "04:30", 595),
]

flights = []
for (city, country, airline, out_no, ret_no, out_price, ret_price,
     out_date, ret_date, out_dep, out_arr, ret_dep, ret_arr, duration) in DESTINATIONS:

    # Outbound: 2 fare options (cheaper with a stop, pricier direct)
    flights.append((airline, out_no, "Sydney", city, out_date, out_dep, out_arr,
                     duration, 0, out_price, 92, 4.5, now))
    flights.append((airline, out_no + "X", "Sydney", city, out_date,
                     "05:45", out_arr, duration + 95, 1, round(out_price * 0.82, 2), 78, 4.1, now))

    # Return: 2 fare options
    flights.append((airline, ret_no, city, "Sydney", ret_date, ret_dep, ret_arr,
                     duration, 0, ret_price, 90, 4.5, now))
    flights.append((airline, ret_no + "X", city, "Sydney", ret_date,
                     "06:30", ret_arr, duration + 95, 1, round(ret_price * 0.82, 2), 76, 4.1, now))

cursor.executemany("""
INSERT INTO flights
(airline, flight_number, origin, destination, departure_date,
 departure_time, arrival_time, duration_minutes, stops, price_aud,
 popularity_score, rating, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", flights)

# ---------------------------------------------------------
# Hotels: 2 in Sydney (the common origin) + 3 per destination,
# spread across budget / mid / luxury price tiers so a budget_aud
# filter actually demonstrates something during a demo.
# ---------------------------------------------------------
hotels = [
    ("Sydney Harbour Hotel",   "Sydney", "2026-11-09", "2026-11-10", 1, 220, 220, 4.7, 95, now),
    ("Central Sydney Suites",  "Sydney", "2026-11-09", "2026-11-10", 1, 150, 150, 4.3, 88, now),
]

HOTEL_TIERS = [
    # (name template, nights, tier, rating, popularity)
    ("{city} Budget Inn",        4, "budget",  4.0, 82),
    ("{city} Central Hotel",     4, "mid",     4.4, 90),
    ("{city} Grand Resort",      4, "luxury",  4.8, 94),
]

TIER_NIGHTLY = {"budget": 85, "mid": 185, "luxury": 340}

for (city, country, *_rest) in DESTINATIONS:
    check_in = [d for d in DESTINATIONS if d[0] == city][0][7]
    check_out = [d for d in DESTINATIONS if d[0] == city][0][8]

    for name_tmpl, nights, tier, rating, popularity in HOTEL_TIERS:
        nightly = TIER_NIGHTLY[tier]
        # Japan hotels run a little higher than AU for the same tier
        if country == "Japan":
            nightly = round(nightly * 1.15, 2)
        total = round(nightly * nights, 2)
        hotels.append((
            name_tmpl.format(city=city), city, check_in, check_out,
            1, nightly, total, rating, popularity, now,
        ))

cursor.executemany("""
INSERT INTO hotels
(name, destination, check_in, check_out, rooms,
 price_per_night_aud, total_price_aud, rating,
 popularity_score, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", hotels)

# ---------------------------------------------------------
# Budgets - one per trip id used across the demo
# ---------------------------------------------------------
budgets = []
for i in range(1, 13):
    total = 1200 + (i * 450)
    budgets.append((i, total, round(total * 0.45, 2), round(total * 0.40, 2), "AUD", now, now))

cursor.executemany("""
INSERT INTO budgets
(trip_id, total_budget, flight_budget, hotel_budget, currency,
 created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", budgets)

# ---------------------------------------------------------
# Trip selections - a believable mix of flights + hotels per trip
# ---------------------------------------------------------
selections = []
sample_cities = [d[0] for d in DESTINATIONS]
for i in range(1, 13):
    city = sample_cities[(i - 1) % len(sample_cities)]
    selections.append((i, "flight", i, f"Sydney \u2192 {city} flight", 180 + (i * 35), now))
    selections.append((i, "hotel", i, f"{city} Central Hotel", 500 + (i * 60), now))

cursor.executemany("""
INSERT INTO trip_selections
(trip_id, item_type, item_id, item_name, price_aud, selected_at)
VALUES (?, ?, ?, ?, ?, ?)
""", selections)

# ---------------------------------------------------------
# Search history - across both countries
# ---------------------------------------------------------
history = []
for i in range(1, 13):
    city = sample_cities[(i - 1) % len(sample_cities)]
    history.append((
        i, "flight" if i % 2 else "hotel", "Sydney", city,
        "2026-11-10", "2026-11-20", 1 + (i % 3), 600 + i * 150,
        f"Round trip to {city}", now,
    ))

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
print(f"Flights: {len(flights)} rows \u2014 round trips (2 fare options each way) "
      f"for 5 AU cities and 5 Japan cities via Sydney.")
print(f"Hotels: {len(hotels)} rows \u2014 2 in Sydney plus budget/mid/luxury tiers "
      f"in all 10 destination cities.")
print(f"Budgets: {len(budgets)} rows. Trip selections: {len(selections)} rows. "
      f"Search history: {len(history)} rows.")