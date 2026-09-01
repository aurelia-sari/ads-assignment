"""Create and seed the Travel Mate database (student-3, Tanishpreet Kour).
 
Owned by student-3. Two tables, each seeded with more than the ten records
the project specification requires. `traveller_id` / `from_traveller_id`
reference the shared `travellers` table in shared.db (see shared/db) by
convention only -- there is no cross-file foreign key, since each database
microservice owns its own SQLite file.
"""
 
import os
import sqlite3
 
DATA_DIR = "./data"
DATABASE_NAME = os.path.join(DATA_DIR, "student3.db")
 
os.makedirs(DATA_DIR, exist_ok=True)
 
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()
 
cursor.execute("""
CREATE TABLE IF NOT EXISTS trip_posts (
    post_id        INTEGER PRIMARY KEY,
    traveller_id   INTEGER NOT NULL,
    destination    TEXT NOT NULL,
    start_date     TEXT NOT NULL,
    end_date       TEXT NOT NULL,
    travel_style   TEXT NOT NULL,
    note           TEXT DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'open',
    created_at     TEXT NOT NULL
)
""")
 
cursor.execute("""
CREATE TABLE IF NOT EXISTS connect_requests (
    request_id        INTEGER PRIMARY KEY,
    from_traveller_id  INTEGER NOT NULL,
    to_post_id          INTEGER NOT NULL,
    message              TEXT DEFAULT '',
    status               TEXT NOT NULL DEFAULT 'pending',
    created_at           TEXT NOT NULL,
    FOREIGN KEY (to_post_id) REFERENCES trip_posts (post_id) ON DELETE CASCADE
)
""")
 
cursor.execute("DELETE FROM connect_requests")
cursor.execute("DELETE FROM trip_posts")
 
trip_posts = [
    (1,  1,  "Bali, Indonesia",         "2026-10-12", "2026-10-19", "into hiking, budget traveller",     "Ubud rice terraces and volcano hikes, chill pace.",            "open",    "2026-08-20"),
    (2,  2,  "Kyoto, Japan",            "2026-11-03", "2026-11-10", "culture and food",                  "First time in Japan, temples and regional food.",             "open",    "2026-08-21"),
    (3,  3,  "Queenstown, NZ",          "2026-12-20", "2026-12-27", "adventure, adrenaline",              "Bungee, skydiving, hiking over the holidays.",                "matched", "2026-08-15"),
    (4,  4,  "Lisbon, Portugal",        "2026-09-14", "2026-09-21", "budget traveller, nightlife",        "City break, cheap eats and live fado music.",                 "open",    "2026-08-22"),
    (5,  5,  "Reykjavik, Iceland",      "2026-08-05", "2026-08-15", "into hiking, photography",           "Ring road campervan trip, northern lights chasing.",          "open",    "2026-08-10"),
    (6,  6,  "Marrakech, Morocco",      "2026-10-25", "2026-11-02", "culture, solo traveller",             "Souks, Atlas mountains day trip, mint tea everywhere.",       "closed",  "2026-08-05"),
    (7,  7,  "Cairns, Australia",       "2026-09-06", "2026-09-13", "diving, budget traveller",           "Great Barrier Reef liveaboard, looking for a dive buddy.",    "open",    "2026-08-18"),
    (8,  8,  "Seoul, South Korea",      "2026-11-20", "2026-11-27", "food, nightlife",                    "Street food crawl and K-pop districts.",                      "open",    "2026-08-24"),
    (9,  9,  "Bergen, Norway",          "2026-07-01", "2026-07-08", "into hiking, nature",                "Fjord hikes, looking for a hiking-fit travel mate.",           "matched", "2026-07-28"),
    (10, 10, "Sri Lanka Tea Country",   "2026-09-28", "2026-10-06", "budget traveller, relaxed pace",     "Trains, tea plantations, slow travel.",                       "open",    "2026-08-19"),
    (11, 11, "Hanoi, Vietnam",          "2026-10-01", "2026-10-08", "food, culture",                      "Old Quarter food tour and cooking class.",                    "open",    "2026-08-23"),
    (12, 12, "Amalfi Coast, Italy",     "2026-06-10", "2026-06-20", "road trip, budget traveller",        "Driving the coast, splitting hire car and fuel costs.",       "open",    "2026-08-12"),
]
 
cursor.executemany(
    """
    INSERT INTO trip_posts (post_id, traveller_id, destination, start_date,
                             end_date, travel_style, note, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    trip_posts,
)
 
connect_requests = [
    (1,  2,  1,  "Hey! Saw we're both into hiking, keen to team up for the volcano trek?",  "pending",  "2026-08-25"),
    (2,  4,  1,  "I'm also budget travelling around that time, mind if I join?",              "pending",  "2026-08-26"),
    (3,  1,  2,  "First time in Kyoto too, would love company for temple hopping.",           "accepted", "2026-08-22"),
    (4,  5,  3,  "I'm chasing an adrenaline-packed itinerary too, keen to split accommodation.", "accepted", "2026-08-16"),
    (5,  6,  4,  "Nightlife sounds great, I'm heading to Lisbon around then as well.",         "pending",  "2026-08-27"),
    (6,  3,  5,  "Northern lights chasing is exactly my thing, can I tag along?",              "declined", "2026-08-11"),
    (7,  9,  6,  "Solo travelling Marrakech too, would be nice to have company for the souks.", "declined", "2026-08-06"),
    (8,  8,  7,  "I'm a certified diver, happy to split the liveaboard cost with you.",        "accepted", "2026-08-19"),
    (9,  10, 8,  "Seoul street food crawl sounds amazing, count me in?",                       "pending",  "2026-08-25"),
    (10, 1,  9,  "I hike regularly, would love to join the fjord trip.",                       "accepted", "2026-07-29"),
    (11, 7,  10, "Slow travel through tea country is exactly my pace too.",                    "pending",  "2026-08-20"),
    (12, 11, 12, "I can drive stick and split fuel costs for the Amalfi road trip.",            "pending",  "2026-08-13"),
]
 
cursor.executemany(
    """
    INSERT INTO connect_requests (request_id, from_traveller_id, to_post_id,
                                   message, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    connect_requests,
)
 
conn.commit()
conn.close()
 
print(
    f"student-3-db initialised with {len(trip_posts)} trip posts "
    f"and {len(connect_requests)} connect requests."
)
 