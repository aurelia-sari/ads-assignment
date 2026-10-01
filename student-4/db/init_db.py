"""Create the Account & Dashboard database (student-4, Aurelia Sari).

User accounts and access logs live in shared-db (see shared/db/init_db.py)
since a user's id and sign-in state are shared data every feature may need.

This database owns the Travel Guides destinations: the cities a guide can be
looked up for. The five Australian and five Japanese cities are the ones the
other features already use, so a traveller can move between features for the
same city.

Runs at every container start, not at build time, so a seed change reaches an
existing volume. It is safe to run repeatedly. Destination ids are fixed so
saved chats keep pointing at the right city.
"""

import os
import sqlite3

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
DATABASE_NAME = os.path.join(DATA_DIR, "student4.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS destinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    region TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    -- IANA name, so the guide opens on the city's own month.
    timezone TEXT
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
    tips TEXT NOT NULL,
    bookable INTEGER NOT NULL DEFAULT 0
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
    -- The average daily high, not the daily mean.
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

# These hold real conversations, so unlike the guide tables above they are
# never wiped on reinit. Only chats for a removed destination are deleted below.
cursor.execute("""
CREATE TABLE IF NOT EXISTS guide_ai_chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    destination_id INTEGER NOT NULL REFERENCES destinations(id),
    created_at TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS guide_ai_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES guide_ai_chat_sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    intent_category TEXT,
    created_at TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS feature_redirect_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    redirect_path_template TEXT NOT NULL
)
""")

# CREATE TABLE IF NOT EXISTS leaves an existing volume's tables as they were,
# so columns added after Release 1 are added here.
def add_column_if_missing(table, column, definition):
    columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

add_column_if_missing("destinations", "latitude", "REAL")
add_column_if_missing("destinations", "longitude", "REAL")
add_column_if_missing("destinations", "timezone", "TEXT")
add_column_if_missing("transportation_infos", "bookable", "INTEGER NOT NULL DEFAULT 0")

cursor.execute("DELETE FROM feature_redirect_map")
cursor.execute("DELETE FROM safety_infos")
cursor.execute("DELETE FROM weather_infos")
cursor.execute("DELETE FROM visa_requirements")
cursor.execute("DELETE FROM transportation_infos")
cursor.execute("DELETE FROM currency_infos")

# Never reuse an id for a different city, or old chats would move to it.
# Ids 5, 6 and 8 to 13 belonged to Australian cities removed after Release 1.
destinations = [
    (1, "Australia", "Sydney", "New South Wales", -33.8688, 151.2093, "Australia/Sydney"),
    (2, "Australia", "Melbourne", "Victoria", -37.8136, 144.9631, "Australia/Melbourne"),
    (3, "Australia", "Brisbane", "Queensland", -27.4698, 153.0251, "Australia/Brisbane"),
    (4, "Australia", "Perth", "Western Australia", -31.9523, 115.8613, "Australia/Perth"),
    (7, "Australia", "Cairns", "Queensland", -16.9186, 145.7781, "Australia/Brisbane"),
    (14, "Japan", "Tokyo", "Tokyo Metropolis", 35.6762, 139.6503, "Asia/Tokyo"),
    (15, "Japan", "Osaka", "Osaka Prefecture", 34.6937, 135.5023, "Asia/Tokyo"),
    (16, "Japan", "Sapporo", "Hokkaido", 43.0618, 141.3545, "Asia/Tokyo"),
    (17, "Japan", "Kyoto", "Kyoto Prefecture", 35.0116, 135.7681, "Asia/Tokyo"),
    (18, "Japan", "Nara", "Nara Prefecture", 34.6851, 135.8048, "Asia/Tokyo"),
]

cursor.executemany(
    "INSERT INTO destinations (id, country, city, region, latitude, longitude, timezone) "
    "VALUES (?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT(id) DO UPDATE SET country = excluded.country, city = excluded.city, "
    "region = excluded.region, latitude = excluded.latitude, longitude = excluded.longitude, "
    "timezone = excluded.timezone",
    destinations,
)

destination_ids = [destination[0] for destination in destinations]
placeholders = ", ".join("?" for _ in destination_ids)
cursor.execute(f"DELETE FROM destinations WHERE id NOT IN ({placeholders})", destination_ids)

# Chats for a removed destination are already hidden from Past chats, so
# delete them rather than leave orphan rows.
cursor.execute(
    "DELETE FROM guide_ai_chat_messages WHERE session_id IN ("
    "SELECT id FROM guide_ai_chat_sessions "
    "WHERE destination_id NOT IN (SELECT id FROM destinations))"
)
removed_chats = cursor.execute(
    "DELETE FROM guide_ai_chat_sessions WHERE destination_id NOT IN (SELECT id FROM destinations)"
).rowcount

CURRENCY_BY_COUNTRY = {
    "Australia": (
        "AUD",
        "Australian Dollar",
        "Cards are accepted almost everywhere. Carry a little cash for small "
        "regional towns and markets. One AUD equals 100 cents.",
    ),
    "Japan": (
        "JPY",
        "Japanese Yen",
        "Cash is still common, especially at small restaurants, shrines and "
        "local shops. Most convenience store ATMs accept foreign cards. The yen "
        "has no smaller unit in everyday use.",
    ),
}

currency_infos = [
    (destination_id, *CURRENCY_BY_COUNTRY[country])
    for destination_id, country, *_ in destinations
]

cursor.executemany(
    "INSERT INTO currency_infos (destination_id, currency_code, currency_name, exchange_tips) "
    "VALUES (?, ?, ?, ?)",
    currency_infos,
)

# Which transport modes each city actually has, so the frontend never shows
# a mode a city does not offer. Kyoto and Nara have no airport.
TRANSPORT_TYPES_BY_CITY = {
    "Sydney": ["flights", "metro", "train", "taxi", "rental"],
    "Melbourne": ["flights", "metro", "train", "taxi", "rental"],
    "Brisbane": ["flights", "metro", "train", "taxi", "rental"],
    "Perth": ["flights", "metro", "train", "taxi", "rental"],
    "Cairns": ["flights", "train", "taxi", "rental"],
    "Tokyo": ["flights", "metro", "train", "taxi", "rental"],
    "Osaka": ["flights", "metro", "train", "taxi", "rental"],
    "Sapporo": ["flights", "metro", "train", "taxi", "rental"],
    "Kyoto": ["metro", "train", "taxi", "rental"],
    "Nara": ["train", "taxi", "rental"],
}

# Only these cities have flights in student-5 (Bookings & Budget), so only
# their Flights tab shows a Book flights button.
FLIGHT_BOOKABLE_CITIES = {"Sydney", "Melbourne", "Brisbane", "Perth", "Cairns"}

AIRPORTS_BY_CITY = {
    "Tokyo": "Haneda and Narita airports",
    "Osaka": "Kansai and Itami airports",
    "Sapporo": "New Chitose Airport",
}

# Train services differ too much between cities for one shared sentence.
TRAIN_COPY_BY_CITY = {
    "Cairns": (
        "The Spirit of Queensland runs between Cairns and Brisbane, and the Kuranda "
        "Scenic Railway climbs into the rainforest.",
        "Reserve seats ahead for long distance trips, especially on weekends and public holidays.",
    ),
    "Tokyo": (
        "Shinkansen bullet trains leave Tokyo Station for Kyoto, Osaka and other major "
        "cities, and JR and private lines cover the wider Tokyo area.",
        "Reserve shinkansen seats ahead for busy holiday periods such as Golden Week and New Year.",
    ),
    "Osaka": (
        "Shinkansen trains stop at Shin-Osaka, and JR and private lines connect Osaka "
        "with Kyoto, Nara and Kansai Airport.",
        "Reserve shinkansen seats ahead for busy holiday periods such as Golden Week and New Year.",
    ),
    "Sapporo": (
        "JR limited express trains connect Sapporo with New Chitose Airport and other "
        "Hokkaido cities. The shinkansen does not reach Sapporo yet.",
        "Snow can delay trains from December to February, so leave extra time.",
    ),
    "Kyoto": (
        "Shinkansen trains stop at Kyoto Station, and the Haruka express runs to Kansai "
        "Airport. Kyoto has no airport of its own, so most visitors fly into Kansai or "
        "Itami in Osaka.",
        "Buses near popular temples get very crowded, so trains are often quicker.",
    ),
    "Nara": (
        "Kintetsu and JR trains connect Nara with Kyoto and Osaka in under an hour. Nara "
        "has no airport or shinkansen station, so most visitors fly into Kansai or Itami "
        "in Osaka.",
        "Most sights are within walking distance of Kintetsu Nara Station.",
    ),
}

def flights_copy(city, country):
    if country == "Japan":
        return (
            f"{city} is served by {AIRPORTS_BY_CITY[city]}, with domestic and international flights.",
            "Check airport train and bus times before a late arrival, since the last "
            "connection into the city can leave early.",
        )
    return (
        f"Regular domestic flights connect {city} to the major Australian airports.",
        "Book early for the best fares and arrive at least 60 minutes before a domestic flight.",
    )

def metro_copy(city, country):
    if country == "Japan":
        return (
            f"{city} has a subway network that covers the main sights and stations.",
            "A rechargeable IC card such as Suica or ICOCA works on the subway, trains "
            "and buses, and in many convenience stores.",
        )
    return (
        f"{city} has a metro and suburban train network connecting the city centre with "
        "the surrounding suburbs.",
        "Buy a reloadable transit card at the airport or a station for the cheapest fares.",
    )

def train_copy(city):
    if city in TRAIN_COPY_BY_CITY:
        return TRAIN_COPY_BY_CITY[city]
    return (
        f"Regional and interstate trains connect {city} with nearby cities and towns.",
        "Reserve seats ahead for long distance trips, especially on weekends and public holidays.",
    )

def taxi_copy(city, country):
    if country == "Japan":
        return (
            f"Taxis are easy to find at stations and taxi ranks throughout {city}. The "
            "rear doors open and close automatically.",
            "Taxi apps such as GO work in the big cities, but rideshare services are limited in Japan.",
        )
    return (
        f"Taxis and rideshare services operate throughout {city} and are easy to find near the "
        "airport and the city centre.",
        "Rideshare apps often work out cheaper than a metered taxi for short trips.",
    )

def rental_copy(city, country):
    if country == "Japan":
        return (
            f"Rental cars are available near {city}'s main stations and are most useful for "
            "trips outside the city.",
            "Japan drives on the left. Most visitors need an International Driving Permit, "
            "and some licences need an official Japanese translation instead.",
        )
    return (
        f"Rental cars are available at {city} airport and in the city centre for exploring at your own pace.",
        "An international licence and a credit card are required for most rental car bookings.",
    )

transportation_infos = []
for destination_id, country, city, *_ in destinations:
    for transport_type in TRANSPORT_TYPES_BY_CITY[city]:
        if transport_type == "flights":
            description, tips = flights_copy(city, country)
        elif transport_type == "metro":
            description, tips = metro_copy(city, country)
        elif transport_type == "train":
            description, tips = train_copy(city)
        elif transport_type == "taxi":
            description, tips = taxi_copy(city, country)
        else:
            description, tips = rental_copy(city, country)
        bookable = int(transport_type == "flights" and city in FLIGHT_BOOKABLE_CITIES)
        transportation_infos.append((destination_id, transport_type, description, tips, bookable))

cursor.executemany(
    "INSERT INTO transportation_infos (destination_id, type, description, tips, bookable) "
    "VALUES (?, ?, ?, ?, ?)",
    transportation_infos,
)

# Visa rules are set by each country's immigration system, not by the city a
# traveller lands in, so every city in a country shares one list. The rules
# are indicative and change over time.
ETA_NOTES = (
    "Apply through the official app for an ETA before you travel. There is a "
    "small service fee and it usually allows stays of up to three months per visit."
)
EVISITOR_NOTES = (
    "Apply online for a free eVisitor visa before you travel. It usually allows "
    "stays of up to three months per visit."
)
AUSTRALIA_VISA_REQUIRED_NOTES = (
    "Apply for a visitor visa before you travel. Processing can take several "
    "weeks, so apply well ahead of your trip."
)

VISA_INFO_BY_COUNTRY = {
    "Australia": [
        ("Australia", "Not required",
         "Australian citizens do not need a visa to enter their own country."),
        ("New Zealand", "Visa on arrival",
         "New Zealand passport holders are granted a Special Category Visa on arrival, "
         "allowing a stay of up to three months."),
        ("United Kingdom", "Electronic visa (eVisitor)", EVISITOR_NOTES),
        ("Germany", "Electronic visa (eVisitor)", EVISITOR_NOTES),
        ("United States", "Electronic travel authority (ETA)", ETA_NOTES),
        ("Singapore", "Electronic travel authority (ETA)", ETA_NOTES),
        ("Japan", "Electronic travel authority (ETA)", ETA_NOTES),
        ("China", "Visa required in advance", AUSTRALIA_VISA_REQUIRED_NOTES),
        ("Indonesia", "Visa required in advance", AUSTRALIA_VISA_REQUIRED_NOTES),
    ],
    "Japan": [
        ("Japan", "Not required",
         "Japanese citizens do not need a visa to enter their own country."),
        ("Australia", "Visa exempt",
         "Australian passport holders can visit Japan for tourism for up to 90 days without a visa."),
        ("New Zealand", "Visa exempt",
         "New Zealand passport holders can visit Japan for tourism for up to 90 days without a visa."),
        ("United Kingdom", "Visa exempt",
         "British passport holders can visit Japan for tourism for up to 90 days without a visa. "
         "The stay can be extended to six months at an immigration office."),
        ("Germany", "Visa exempt",
         "German passport holders can visit Japan for tourism for up to 90 days without a visa. "
         "The stay can be extended to six months at an immigration office."),
        ("United States", "Visa exempt",
         "United States passport holders can visit Japan for tourism for up to 90 days without a visa."),
        ("Singapore", "Visa exempt",
         "Singapore passport holders can visit Japan for tourism for up to 30 days without a visa."),
        ("China", "Visa required in advance",
         "Apply for a visitor visa through a Japanese embassy or an approved agency before you "
         "travel. Allow several weeks for processing."),
        ("Indonesia", "Visa waiver registration",
         "Holders of an Indonesian ePassport can register for a visa waiver before travel and "
         "stay up to 15 days. Other passport holders need a visa in advance."),
    ],
}

visa_requirements = [
    (destination_id, nationality, requirement_type, notes)
    for destination_id, country, *_ in destinations
    for nationality, requirement_type, notes in VISA_INFO_BY_COUNTRY[country]
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

KANSAI_BEST_VISIT = (
    "Late March to early April and November are the most popular months, for cherry "
    "blossom and autumn leaves. July and August are hot and humid."
)

# Average daily high (Celsius) and rainfall (mm) per month, rounded from each
# city's long-term station averages. Australian figures are Bureau of
# Meteorology averages for Sydney Observatory Hill (1991 to 2020), Melbourne
# CBD (1991 to 2015), Brisbane City (1999 to 2024), Perth Metro (1993 to 2020)
# and Cairns Aero (1991 to 2020). Japanese figures are each city's JMA 1991 to
# 2020 normals.
WEATHER_PROFILES = {
    "sydney": (
        [
            (27, 91), (27, 132), (26, 118), (24, 114), (21, 101), (18, 142),
            (18, 80), (19, 75), (22, 63), (23, 68), (24, 91), (26, 73),
        ],
        "September to November and March to May bring warm days without summer humidity.",
    ),
    "melbourne": (
        [
            (27, 44), (27, 50), (25, 39), (21, 53), (18, 44), (15, 50),
            (15, 40), (16, 47), (18, 55), (21, 56), (23, 63), (25, 61),
        ],
        "March to May and November bring mild days, but the weather can change quickly "
        "within a single day.",
    ),
    "brisbane": (
        [
            (30, 141), (30, 182), (29, 129), (27, 61), (25, 70), (22, 57),
            (22, 30), (24, 35), (26, 30), (27, 86), (28, 100), (30, 140),
        ],
        "April to October has warm days, lower humidity and less rain than summer.",
    ),
    "perth": (
        [
            (31, 17), (32, 13), (30, 20), (26, 36), (22, 86), (20, 127),
            (19, 147), (19, 123), (21, 79), (24, 40), (27, 24), (30, 9),
        ],
        "March to April and October to November bring warm days with little rain.",
    ),
    "cairns": (
        [
            (32, 389), (32, 476), (31, 367), (30, 178), (28, 81), (27, 43),
            (26, 36), (27, 27), (29, 28), (30, 63), (31, 85), (32, 186),
        ],
        "May to October, the dry season, has sunny days and much less rain than summer.",
    ),
    "tokyo": (
        [
            (10, 60), (11, 57), (14, 116), (19, 134), (24, 140), (26, 168),
            (30, 156), (31, 155), (28, 225), (22, 235), (17, 96), (12, 58),
        ],
        "Late March to May and October to November are mild, with cherry blossom in spring "
        "and autumn leaves in November. June and early July are the rainy season.",
    ),
    "osaka": (
        [
            (10, 47), (11, 61), (14, 103), (20, 102), (25, 137), (28, 185),
            (32, 174), (34, 113), (30, 153), (24, 136), (18, 73), (12, 56),
        ],
        KANSAI_BEST_VISIT,
    ),
    "kyoto": (
        [
            (9, 53), (10, 65), (14, 106), (20, 117), (25, 151), (28, 200),
            (32, 224), (34, 154), (29, 179), (23, 143), (17, 74), (12, 57),
        ],
        KANSAI_BEST_VISIT,
    ),
    "nara": (
        [
            (9, 52), (10, 63), (14, 105), (20, 99), (25, 139), (28, 184),
            (32, 174), (33, 128), (29, 159), (23, 135), (17, 71), (12, 57),
        ],
        KANSAI_BEST_VISIT,
    ),
    "hokkaido": (
        [
            (0, 108), (0, 92), (5, 78), (12, 55), (18, 56), (22, 60),
            (25, 91), (26, 127), (23, 142), (16, 110), (9, 114), (2, 115),
        ],
        "June to August is mild and fairly dry for sightseeing. December to February "
        "brings heavy snow, good skiing and the Sapporo Snow Festival in February.",
    ),
}

WEATHER_PROFILE_BY_CITY = {
    "Sydney": "sydney",
    "Melbourne": "melbourne",
    "Brisbane": "brisbane",
    "Perth": "perth",
    "Cairns": "cairns",
    "Tokyo": "tokyo",
    "Osaka": "osaka",
    "Kyoto": "kyoto",
    "Nara": "nara",
    "Sapporo": "hokkaido",
}

weather_infos = []
for destination_id, country, city, *_ in destinations:
    monthly_figures, best_visit_time = WEATHER_PROFILES[WEATHER_PROFILE_BY_CITY[city]]
    for month, (avg_temp, rainfall) in zip(MONTHS, monthly_figures):
        weather_infos.append((destination_id, month, avg_temp, rainfall, best_visit_time))

cursor.executemany(
    "INSERT INTO weather_infos (destination_id, month, avg_temp, rainfall, best_visit_time) "
    "VALUES (?, ?, ?, ?, ?)",
    weather_infos,
)

# Australia's Smartraveller advisory currently gives Japan its lowest level,
# the same level used here for Australia, so only the tips vary by city.
SAFETY_LEVEL = "Exercise normal safety precautions"

EARTHQUAKE_TIP = "Earthquakes can happen at any time, so learn the exit routes where you stay."

SAFETY_TIPS_BY_CITY = {
    "Sydney": "Take care of surf conditions and rips at ocean beaches. Watch your "
              "belongings in busy tourist areas.",
    "Melbourne": "The weather can change quickly, so carry a jacket even in summer. "
                 "Stay aware of your belongings on trams and in busy laneways.",
    "Brisbane": "Summer storms can be sudden and severe. Use sun protection, since UV "
                "levels are high for most of the year.",
    "Perth": "Summer heat can be intense, so stay hydrated and use sun protection. "
             "Ocean currents can be strong at unpatrolled beaches.",
    "Cairns": "Do not swim in the ocean during stinger season without a protective "
              "suit. Only swim in patrolled, netted areas.",
    "Tokyo": f"{EARTHQUAKE_TIP} In nightlife areas such as Kabukicho and Roppongi, watch "
             "for drink spiking and inflated bar bills.",
    "Osaka": f"{EARTHQUAKE_TIP} Typhoons are most likely from August to October, so check "
             "the forecast before day trips.",
    "Sapporo": "Footpaths and roads are icy in winter, so wear shoes with good grip. Check "
               "avalanche warnings before skiing off the marked runs.",
    "Kyoto": "Summer heat can be intense, so stay hydrated. Popular temples and lanes get "
             "very crowded, so watch your belongings and follow the no photography signs in Gion.",
    "Nara": "The park deer are wild and can bite or butt when they expect food, so do not "
            f"tease them. {EARTHQUAKE_TIP}",
}

safety_infos = [
    (destination_id, SAFETY_LEVEL, SAFETY_TIPS_BY_CITY[city])
    for destination_id, country, city, *_ in destinations
]

cursor.executemany(
    "INSERT INTO safety_infos (destination_id, safety_level, tips) VALUES (?, ?, ?)",
    safety_infos,
)

# Keywords the AI assistant uses to redirect a question about another
# feature instead of trying to answer it from guide data it does not own.
feature_redirect_map = [
    ("itinerary", "Trips & Itinerary", "/student-1/"),
    ("day plan", "Trips & Itinerary", "/student-1/"),
    ("plan my trip", "Trips & Itinerary", "/student-1/"),
    ("restaurant", "Attractions & Dining", "/student-2/"),
    ("attraction", "Attractions & Dining", "/student-2/"),
    ("sightseeing", "Attractions & Dining", "/student-2/"),
    ("things to do", "Attractions & Dining", "/student-2/"),
    ("food", "Attractions & Dining", "/student-2/"),
    ("travel mate", "Travel Mate", "/student-3/"),
    ("travel buddy", "Travel Mate", "/student-3/"),
    ("travel companion", "Travel Mate", "/student-3/"),
    ("book a flight", "Bookings & Budget", "/student-5/#search"),
    ("book flight", "Bookings & Budget", "/student-5/#search"),
    ("book a hotel", "Bookings & Budget", "/student-5/#search"),
    ("hotel", "Bookings & Budget", "/student-5/#search"),
    ("budget", "Bookings & Budget", "/student-5/#search"),
]

cursor.executemany(
    "INSERT INTO feature_redirect_map (keyword, feature_name, redirect_path_template) "
    "VALUES (?, ?, ?)",
    feature_redirect_map,
)

conn.commit()
conn.close()

print("student-4-db initialised.")
print(f"Tables: destinations ({len(destinations)} seed records), "
      f"currency_infos ({len(currency_infos)} seed records), "
      f"transportation_infos ({len(transportation_infos)} seed records), "
      f"visa_requirements ({len(visa_requirements)} seed records), "
      f"weather_infos ({len(weather_infos)} seed records), "
      f"safety_infos ({len(safety_infos)} seed records), "
      f"feature_redirect_map ({len(feature_redirect_map)} seed records). "
      f"Saved chats kept, {removed_chats} for removed destinations deleted.")
