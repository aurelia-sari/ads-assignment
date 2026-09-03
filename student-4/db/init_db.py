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

cursor.execute("""
CREATE TABLE IF NOT EXISTS transportation_infos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id INTEGER NOT NULL REFERENCES destinations(id),
    type TEXT NOT NULL,
    description TEXT NOT NULL,
    tips TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS visa_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id INTEGER NOT NULL REFERENCES destinations(id),
    nationality TEXT NOT NULL,
    requirement_type TEXT NOT NULL,
    notes TEXT NOT NULL
)
""")

cursor.execute("DELETE FROM visa_requirements")
cursor.execute("DELETE FROM transportation_infos")
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

# Which transport modes each city actually has, so the frontend never has to
# a mode and a booking button a city does not offer.
TRANSPORT_TYPES_BY_CITY = {
    "Sydney": ["flights", "metro", "train", "taxi", "rental"],
    "Melbourne": ["flights", "metro", "train", "taxi", "rental"],
    "Brisbane": ["flights", "metro", "train", "taxi", "rental"],
    "Perth": ["flights", "metro", "train", "taxi", "rental"],
    "Adelaide": ["flights", "metro", "train", "taxi", "rental"],
    "Gold Coast": ["flights", "metro", "taxi", "rental"],
    "Canberra": ["flights", "metro", "taxi", "rental"],
    "Cairns": ["flights", "taxi", "rental"],
    "Hobart": ["flights", "taxi", "rental"],
    "Darwin": ["flights", "taxi", "rental"],
    "Sunshine Coast": ["flights", "taxi", "rental"],
    "Launceston": ["flights", "taxi", "rental"],
    "Alice Springs": ["flights", "taxi", "rental"],
}

# Gold Coast and Canberra have light rail rather than a full metro network.
LIGHT_RAIL_CITIES = {"Gold Coast", "Canberra"}

def flights_copy(city):
    return (
        f"Regular domestic flights connect {city} to the major Australian airports.",
        "Book early for the best fares and arrive at least 60 minutes before a domestic flight.",
    )

def metro_copy(city, light_rail):
    network = "light rail line" if light_rail else "metro and suburban train network"
    return (
        f"{city} has a {network} connecting the city centre with the surrounding suburbs.",
        "Buy a reloadable transit card at the airport or a station for the cheapest fares.",
    )

def train_copy(city):
    return (
        f"Regional and interstate trains connect {city} with nearby cities and towns.",
        "Reserve seats ahead for long distance trips, especially on weekends and public holidays.",
    )

def taxi_copy(city):
    return (
        f"Taxis and rideshare services operate throughout {city} and are easy to find near the "
        "airport and the city centre.",
        "Rideshare apps often work out cheaper than a metered taxi for short trips.",
    )

def rental_copy(city):
    return (
        f"Rental cars are available at {city} airport and in the city centre for exploring at your own pace.",
        "An international licence and a credit card are required for most rental car bookings.",
    )

transportation_infos = []
for (country, city, region), destination_id in zip(destinations, destination_ids):
    for transport_type in TRANSPORT_TYPES_BY_CITY[city]:
        if transport_type == "flights":
            description, tips = flights_copy(city)
        elif transport_type == "metro":
            description, tips = metro_copy(city, light_rail=city in LIGHT_RAIL_CITIES)
        elif transport_type == "train":
            description, tips = train_copy(city)
        elif transport_type == "taxi":
            description, tips = taxi_copy(city)
        else:
            description, tips = rental_copy(city)
        transportation_infos.append((destination_id, transport_type, description, tips))

cursor.executemany(
    "INSERT INTO transportation_infos (destination_id, type, description, tips) VALUES (?, ?, ?, ?)",
    transportation_infos,
)

# Visa rules are set by Australia's immigration system, not by which city a
# traveller lands in, so every destination shares the same set of
# nationalities and requirements.
VISA_INFO_BY_NATIONALITY = [
    (
        "Australia",
        "Not required",
        "Australian citizens do not need a visa to enter their own country.",
    ),
    (
        "New Zealand",
        "Visa on arrival",
        "New Zealand passport holders are granted a Special Category Visa on arrival, "
        "allowing a stay of up to three months.",
    ),
    (
        "United Kingdom",
        "Electronic visa (eVisitor)",
        "Apply online for a free eVisitor visa before you travel. It usually allows "
        "stays of up to three months per visit.",
    ),
    (
        "Germany",
        "Electronic visa (eVisitor)",
        "Apply online for a free eVisitor visa before you travel. It usually allows "
        "stays of up to three months per visit.",
    ),
    (
        "United States",
        "Electronic travel authority (ETA)",
        "Apply through the official app for an ETA before you travel. There is a "
        "small service fee and it usually allows stays of up to three months per visit.",
    ),
    (
        "Singapore",
        "Electronic travel authority (ETA)",
        "Apply through the official app for an ETA before you travel. There is a "
        "small service fee and it usually allows stays of up to three months per visit.",
    ),
    (
        "China",
        "Visa required in advance",
        "Apply for a visitor visa before you travel. Processing can take several "
        "weeks, so apply well ahead of your trip.",
    ),
    (
        "Indonesia",
        "Visa required in advance",
        "Apply for a visitor visa before you travel. Processing can take several "
        "weeks, so apply well ahead of your trip.",
    ),
]

visa_requirements = [
    (destination_id, nationality, requirement_type, notes)
    for destination_id in destination_ids
    for nationality, requirement_type, notes in VISA_INFO_BY_NATIONALITY
]

cursor.executemany(
    "INSERT INTO visa_requirements (destination_id, nationality, requirement_type, notes) "
    "VALUES (?, ?, ?, ?)",
    visa_requirements,
)

conn.commit()
conn.close()

print("student-4-db initialised.")
print(f"Tables: destinations ({len(destinations)} seed records), "
      f"currency_infos ({len(currency_infos)} seed records), "
      f"transportation_infos ({len(transportation_infos)} seed records), "
      f"visa_requirements ({len(visa_requirements)} seed records).")
