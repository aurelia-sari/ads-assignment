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

cursor.execute("""
CREATE TABLE IF NOT EXISTS weather_infos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id INTEGER NOT NULL REFERENCES destinations(id),
    month TEXT NOT NULL,
    avg_temp REAL NOT NULL,
    rainfall REAL NOT NULL,
    best_visit_time TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS safety_infos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id INTEGER NOT NULL REFERENCES destinations(id),
    safety_level TEXT NOT NULL,
    tips TEXT NOT NULL
)
""")

cursor.execute("DELETE FROM safety_infos")
cursor.execute("DELETE FROM weather_infos")
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

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Average temperature (Celsius) and rainfall (mm) per month, Southern
# Hemisphere seasons, grouped by climate rather than repeated per city.
WEATHER_PROFILES = {
    "mild_temperate": (
        [
            (26, 100), (26, 110), (25, 130), (22, 120), (19, 130), (17, 130),
            (16, 100), (17, 80), (19, 70), (21, 80), (23, 90), (25, 80),
        ],
        "September to November and March to May bring warm days without summer humidity.",
    ),
    "cool_temperate": (
        [
            (17, 45), (17, 40), (16, 50), (14, 55), (11, 55), (9, 55),
            (8, 55), (9, 50), (11, 55), (13, 60), (14, 55), (16, 50),
        ],
        "December to February has the warmest and driest weather for outdoor activities.",
    ),
    "subtropical": (
        [
            (29, 140), (29, 150), (27, 120), (25, 80), (22, 70), (20, 60),
            (19, 50), (20, 40), (23, 40), (25, 70), (27, 90), (28, 110),
        ],
        "April to October has warm days, lower humidity and less rain than summer.",
    ),
    "mediterranean": (
        [
            (30, 10), (30, 15), (28, 20), (24, 40), (21, 80), (18, 120),
            (17, 120), (18, 90), (19, 60), (22, 40), (25, 20), (28, 15),
        ],
        "September to November and March to May bring warm days with little rain.",
    ),
    "tropical_wet_dry": (
        [
            (31, 400), (31, 380), (30, 320), (29, 150), (28, 60), (26, 30),
            (26, 20), (27, 20), (28, 30), (30, 50), (31, 120), (31, 250),
        ],
        "May to October, the dry season, has sunny days and much less rain than summer.",
    ),
    "arid": (
        [
            (36, 40), (35, 45), (32, 30), (27, 15), (22, 15), (19, 15),
            (19, 10), (22, 10), (27, 10), (31, 20), (33, 30), (35, 40),
        ],
        "May to September has mild days and cold nights, avoiding the extreme summer heat.",
    ),
}

WEATHER_PROFILE_BY_CITY = {
    "Sydney": "mild_temperate",
    "Melbourne": "mild_temperate",
    "Adelaide": "mild_temperate",
    "Canberra": "cool_temperate",
    "Hobart": "cool_temperate",
    "Launceston": "cool_temperate",
    "Brisbane": "subtropical",
    "Gold Coast": "subtropical",
    "Sunshine Coast": "subtropical",
    "Perth": "mediterranean",
    "Cairns": "tropical_wet_dry",
    "Darwin": "tropical_wet_dry",
    "Alice Springs": "arid",
}

weather_infos = []
for (country, city, region), destination_id in zip(destinations, destination_ids):
    monthly_figures, best_visit_time = WEATHER_PROFILES[WEATHER_PROFILE_BY_CITY[city]]
    for month, (avg_temp, rainfall) in zip(MONTHS, monthly_figures):
        weather_infos.append((destination_id, month, avg_temp, rainfall, best_visit_time))

cursor.executemany(
    "INSERT INTO weather_infos (destination_id, month, avg_temp, rainfall, best_visit_time) "
    "VALUES (?, ?, ?, ?, ?)",
    weather_infos,
)

# Use Australia's official government travel advisory for the whole country
# one safety level, so only the tips vary, by what actually differs city to
# city (surf, wildlife, heat, weather).
SAFETY_LEVEL = "Exercise normal safety precautions"

SAFETY_TIPS_BY_CITY = {
    "Sydney": "Take care of surf conditions and rips at ocean beaches. Watch your "
              "belongings in busy tourist areas.",
    "Melbourne": "The weather can change quickly, so carry a jacket even in summer. "
                 "Stay aware of your belongings on trams and in busy laneways.",
    "Brisbane": "Summer storms can be sudden and severe. Use sun protection, since UV "
                "levels are high for most of the year.",
    "Perth": "Summer heat can be intense, so stay hydrated and use sun protection. "
             "Ocean currents can be strong at unpatrolled beaches.",
    "Adelaide": "Summer heatwaves can be extreme, so stay hydrated and avoid the "
                "midday sun. Take care crossing tram tracks in the city centre.",
    "Gold Coast": "Swim between the flags at patrolled beaches, since surf conditions "
                  "can be strong. Use sun protection year round.",
    "Cairns": "Do not swim in the ocean during stinger season without a protective "
              "suit. Only swim in patrolled, netted areas.",
    "Canberra": "Winters can be cold with occasional frost, so pack warm clothing. "
                "Watch for wildlife on roads at dawn and dusk.",
    "Hobart": "Weather can turn cold and wet quickly, even in summer, so pack layers. "
              "Take care on unmarked bushwalking trails.",
    "Darwin": "Do not swim in rivers, waterholes or the ocean without checking for "
              "crocodile warnings. The wet season brings heavy storms.",
    "Sunshine Coast": "Swim between the flags at patrolled beaches, since surf "
                       "conditions can be strong. Use sun protection year round.",
    "Launceston": "Weather can turn cold and wet quickly, even in summer, so pack "
                  "layers. Take care on unmarked bushwalking trails.",
    "Alice Springs": "Carry plenty of water and tell someone your plans before remote "
                      "bushwalks. Summer heat can be extreme, so avoid the midday sun.",
}

safety_infos = [
    (destination_id, SAFETY_LEVEL, SAFETY_TIPS_BY_CITY[city])
    for (country, city, region), destination_id in zip(destinations, destination_ids)
]

cursor.executemany(
    "INSERT INTO safety_infos (destination_id, safety_level, tips) VALUES (?, ?, ?)",
    safety_infos,
)

conn.commit()
conn.close()

print("student-4-db initialised.")
print(f"Tables: destinations ({len(destinations)} seed records), "
      f"currency_infos ({len(currency_infos)} seed records), "
      f"transportation_infos ({len(transportation_infos)} seed records), "
      f"visa_requirements ({len(visa_requirements)} seed records), "
      f"weather_infos ({len(weather_infos)} seed records), "
      f"safety_infos ({len(safety_infos)} seed records).")
