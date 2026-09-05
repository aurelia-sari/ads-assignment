"""
Initialise and seed the Student 2 SQLite database. (student-2, Kevin Kim)

Release 0 - Attractions & Dining

Creates and seeds:
- places
- favourites
- recommendations

Each table contains at least 10 records as required by the
Release 0 project specification.

The script is idempotent.
Existing table data is preserved when the script is re-run.
Re-check or replace the image URL if it stops resolving.
"""



import json
import os
import sqlite3
from pathlib import Path


# ------------------------------------------------------------------
# Database configuration
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = Path(
    os.environ.get(
        "DB_PATH",
        BASE_DIR / "data" / "student2.db"
    )
)


# ------------------------------------------------------------------
# Seed data - Places
# ------------------------------------------------------------------

# Representative photo for each place, taken directly from that
# place's Google Maps listing (lh3.googleusercontent.com CDN).
# NOTE: these are unofficial Google Maps photo URLs (not the paid
# Places API). They are good enough for the current demo video, but
# are not guaranteed to stay valid indefinitely - re-scrape from
# Google Maps if any of them stop resolving.
GOOGLE_MAPS_PHOTO = "https://lh3.googleusercontent.com/gps-cs-s/{}"


PLACES = [
    {
        "external_place_id": None,
        "name": "Sydney Opera House",
        "category": "attraction",
        "address": "Bennelong Point, Sydney NSW 2000",
        "latitude": -33.8568,
        "longitude": 151.2153,
        "rating": 4.8,
        "opening_hours": "09:00-17:00",
        "price_range": 0,
        "description": (
            "Iconic performing arts venue located on Sydney Harbour."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWnDJ75Mz0JyGRx-UtUH9Sp9HBf13PogCckXS3R3POPXGJYgdp-3RlLU"
            "RNEo7mWmuEziU62_9zziKFXUEFM7rdf0glcDnPVU9OAWaBcOhEww5YfO1yef"
            "rYOzNQKQfHBcOOX9rjX9=w408-h306-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Sydney Harbour Bridge",
        "category": "attraction",
        "address": "Sydney Harbour Bridge, Sydney NSW 2000",
        "latitude": -33.8523,
        "longitude": 151.2108,
        "rating": 4.8,
        "opening_hours": "00:00-23:59",
        "price_range": 0,
        "description": (
            "Iconic steel arch bridge connecting Sydney CBD "
            "and the North Shore."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWk-hYefwc_wTTUCkH6PwVN5J7UYfj2zsrEqsQrhNMe8G45VnfUT7-i2"
            "vUBkpvqj014Xm2uBQlJ6EPAjczUABhXhQ6Orhn-49gT6q649n4SBpoe1EOyp"
            "1IkFDJSfUg7JsVZH9Msm=w408-h306-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Taronga Zoo",
        "category": "attraction",
        "address": "Bradleys Head Rd, Mosman NSW 2088",
        "latitude": -33.8433,
        "longitude": 151.2412,
        "rating": 4.5,
        "opening_hours": "09:30-16:30",
        "price_range": 50,
        "description": (
            "Harbourside zoo featuring native "
            "and international wildlife."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWneYgtx9Dx9pqjy1KQRKb8nujythQN5ZpCobOJhaFfIhU-YO-nxLJgs"
            "NtVfzFpFDtjelZsapJr1bUhFmSYzdJW7gmSSfHARowXrtTBTZUmRW4mtf_dl"
            "cwXyfQqjlbU09ikxCyO7x0hH_e_E=w408-h269-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Royal Botanic Garden Sydney",
        "category": "attraction",
        "address": "Mrs Macquaries Rd, Sydney NSW 2000",
        "latitude": -33.8642,
        "longitude": 151.2166,
        "rating": 4.7,
        "opening_hours": "07:00-17:00",
        "price_range": 0,
        "description": (
            "Large historic botanical garden beside Sydney Harbour."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWn_HFOiA1joD_6pWC3zRJHBo2RGJxmkJJjY5yhV-76wPJrMaKXq-kxO"
            "0nMur243o2ApA5miayGSd6cWQkKaMXbamnz7vIDwe_k-4ibRHoD-ZS8-wdW1"
            "6ripiCc08-Vz5uxB3KW10g=w408-h306-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Bondi Beach",
        "category": "attraction",
        "address": "Bondi Beach NSW 2026",
        "latitude": -33.8908,
        "longitude": 151.2743,
        "rating": 4.6,
        "opening_hours": "00:00-23:59",
        "price_range": 0,
        "description": (
            "Popular Sydney beach known for surfing and coastal walks."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWkGIdEDUbT5cy1O7W_VwzmWdfdPFobcUZ7Y4__hz-c0BMySeSVpNJX-"
            "-97YHUt7-uzTfCFJq3NzewywDH2z9KKBdAUMmqZ5IoLt8FPybRfMjRGPHc2h"
            "u5gPhZpXnP9R1rXrDgdQsaJhwaYN=w408-h306-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "The Rocks",
        "category": "attraction",
        "address": "The Rocks NSW 2000",
        "latitude": -33.8599,
        "longitude": 151.2090,
        "rating": 4.6,
        "opening_hours": "00:00-23:59",
        "price_range": 0,
        "description": (
            "Historic Sydney precinct with markets, restaurants "
            "and harbour views."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWkdc83097jjvMKJOtC67ETdYGy7Z685J4vxg_WlxIGfE52q7Sp4ZEhI"
            "XWVy-MyHYRULlylqB3nEesfeGoVZFRq9YETFw80AM8bFs9aBGf5fKItqiHIL"
            "sCHLnulc_xWOVVyd6s04=w408-h306-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Manly Beach",
        "category": "attraction",
        "address": "Manly NSW 2095",
        "latitude": -33.7969,
        "longitude": 151.2879,
        "rating": 4.7,
        "opening_hours": "00:00-23:59",
        "price_range": 0,
        "description": (
            "Popular beach destination accessible by ferry "
            "from Circular Quay."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWmTJ_j8hOWSdGeY5a9nqryKziYv2Sqh_d4AQDOPpGGVLgUvhPD4JSYs"
            "hN04ynaohC6m5wkvBaAXYqZH1zjWD66SZR9V60FJXqs5hBS05XLmydtYyJ05"
            "5qljevfThrTsJ0hv1hbZ=w433-h240-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Art Gallery of New South Wales",
        "category": "attraction",
        "address": "Art Gallery Rd, Sydney NSW 2000",
        "latitude": -33.8688,
        "longitude": 151.2173,
        "rating": 4.7,
        "opening_hours": "10:00-17:00",
        "price_range": 0,
        "description": (
            "Major public art museum located beside The Domain."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWm3Jpr_38pUbuecUCPYy9LL_T7icCXt6GnGREwt0V3D4lh1VDYmge7V"
            "UhsrTvPF461yLX2hi3ScnWxhgeLVe7iZIM1lykqO-u0JYR_4D8N862kihOi8"
            "2TUhFlkCmF_mbC91xJFXO11YoeXg=w408-h306-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Harry's Cafe de Wheels",
        "category": "restaurant",
        "address": "1 Cowper Wharf Rd, Woolloomooloo NSW 2011",
        "latitude": -33.8688,
        "longitude": 151.2225,
        "rating": 4.3,
        "opening_hours": "09:00-22:00",
        "price_range": 10,
        "description": (
            "Popular Sydney food venue known for pies and hot dogs."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWnMjSEKGa68k30MEyeYV308mP8OUbpfsc9nxJjbCDjtB3NbKzV2uFZb"
            "JqKrfR-mhYmzYORZNyrQMNCcT3oxqBWK5B0_j8jK-trM_lcW22gJRnPnJOVT"
            "z2bW84PINVQsI9go9KXL=w408-h271-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Chat Thai Haymarket",
        "category": "restaurant",
        "address": "20 Campbell St, Haymarket NSW 2000",
        "latitude": -33.8793,
        "longitude": 151.2044,
        "rating": 4.0,
        "opening_hours": "10:00-22:00",
        "price_range": 30,
        "description": (
            "Thai restaurant offering a range of traditional dishes."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWlHAbZyOcNw0daqEGzuaJXirsb_CUv8J_Je0bbO1Q6pXF8IOgMyaVJF"
            "FDKm842M8nThHU17tmltvg7JYFRxptAw4cKC5t_24RXmfyLIUbudVoywWtLF"
            "qkw24Lilq-6Ckhbk0Wuoxg=w408-h306-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Mamak",
        "category": "restaurant",
        "address": "15 Goulburn St, Haymarket NSW 2000",
        "latitude": -33.8797,
        "longitude": 151.2058,
        "rating": 4.3,
        "opening_hours": "11:30-22:00",
        "price_range": 30,
        "description": (
            "Malaysian restaurant popular for roti "
            "and traditional dishes."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWnxQaM4GboSENWHqnNTKongCLvkGa2TNP_fPoWUDoelsZxAcop5M3Et"
            "MQUIK6amhI_Iwha_ENGDhb9baZY06-Kg0OFqOvEFtZTAYzjA6WjAiDmM4ivZ"
            "_8Y7fxQf47KhBWS5JAnO=w512-h240-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "The Grounds of Alexandria",
        "category": "restaurant",
        "address": "2 Huntley St, Alexandria NSW 2015",
        "latitude": -33.9056,
        "longitude": 151.1943,
        "rating": 4.0,
        "opening_hours": "07:30-21:00",
        "price_range": 30,
        "description": (
            "Large cafe and garden precinct known for brunch and coffee."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWlKfO6YDIOBcriDrcHVI4nWDk7t7uZvGttxBcPBwItOEvbM-nchbRoJ"
            "tGeZERKiCXTHeE_ivW34fhgtq-P_ORLyRZ5MsGrgnVnBwKju8MV09uGltwMK"
            "E_0tCCqL3o6-p2vQ-5k=w408-h271-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Mr Wong",
        "category": "restaurant",
        "address": "3 Bridge Ln, Sydney NSW 2000",
        "latitude": -33.8659,
        "longitude": 151.2073,
        "rating": 4.4,
        "opening_hours": "12:00-24:00",
        "price_range": 70,
        "description": "Cantonese restaurant located in Sydney CBD.",
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWmgvkRwI_3H7riP8_AleCpoURJ1OJrtvpXS8nXbG7Yr_R_NK3DS9ImC"
            "Uc8-YQ80Si37hTytVf0-7xwXzWjLVWbLQiR0qOQVvkGQHaVWdUs-yfnCkze3"
            "1TZ9fBtsvoZZfY9EgfXG_A=w408-h256-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Bourke Street Bakery",
        "category": "restaurant",
        "address": "633 Bourke St, Surry Hills NSW 2010",
        "latitude": -33.8886,
        "longitude": 151.2115,
        "rating": 4.5,
        "opening_hours": "07:00-18:00",
        "price_range": 10,
        "description": (
            "Popular bakery offering pastries, bread and cafe meals."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWlwWIGYg9aey-knB_CD0Y42JOCDcbvMCdO_DKA390rD1amLTTh_BXDQ"
            "I7rNEYtFMya8KVlW-OPVwK_ZoSckcj18I6sKMvmzTtbZckzJwUoY9-NBzK-F"
            "HWOmHb8ey2djiY3arwtA=w408-h285-k-no"
        ),
    },
    {
        "external_place_id": None,
        "name": "Gelato Messina Darlinghurst",
        "category": "restaurant",
        "address": "241 Victoria St, Darlinghurst NSW 2010",
        "latitude": -33.8776,
        "longitude": 151.2216,
        "rating": 4.6,
        "opening_hours": "12:00-22:30",
        "price_range": 10,
        "description": (
            "Popular gelato shop offering a rotating range of flavours."
        ),
        "image_url": GOOGLE_MAPS_PHOTO.format(
            "AHRPTWnJJHy8R8Gr1bJt3oiKRX83ZwsvCOBjPVy1AUhb4_x8CiSsP8mkUmSU"
            "7f8xb4fIe1Dy1SDiD2Hz4A3IGqulMrBvlPaguTzK2vWcoxCgQgUtwRhHlzmp"
            "lK7M2XqFV6zcp3pKYZc=w426-h240-k-no"
        ),
    },
]


# ------------------------------------------------------------------
# Database connection
# ------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Create and return a SQLite connection."""

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    return conn


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

def create_schema(conn: sqlite3.Connection) -> None:
    """Create Student 2 database tables."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS places (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_place_id TEXT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            address TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            rating REAL,
            opening_hours TEXT,
            price_range INTEGER,
            description TEXT,
            image_url TEXT
        );

        CREATE TABLE IF NOT EXISTS favourites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            place_id INTEGER NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (place_id)
                REFERENCES places(id)
                ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER ,
            question TEXT NOT NULL,
            preferences TEXT,
            location TEXT,
            recommendation_result TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        """
    )

    conn.commit()


# ------------------------------------------------------------------
# Places seed
# ------------------------------------------------------------------

def seed_places(conn: sqlite3.Connection) -> None:
    """Insert initial place records when the places table is empty."""

    count = conn.execute(
        "SELECT COUNT(*) AS count FROM places"
    ).fetchone()["count"]

    if count > 0:
        print(f"places already contains {count} rows - skipping.")
        return

    for place in PLACES:
        conn.execute(
            """
            INSERT INTO places (
                external_place_id,
                name,
                category,
                address,
                latitude,
                longitude,
                rating,
                opening_hours,
                price_range,
                description,
                image_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                place["external_place_id"],
                place["name"],
                place["category"],
                place["address"],
                place["latitude"],
                place["longitude"],
                place["rating"],
                place["opening_hours"],
                place["price_range"],
                place["description"],
                place["image_url"],
            ),
        )

    conn.commit()

    print(f"Seeded {len(PLACES)} places.")


# ------------------------------------------------------------------
# Favourites seed
# ------------------------------------------------------------------

def seed_favourites(conn: sqlite3.Connection) -> None:
    """Insert at least 10 favourite records."""

    count = conn.execute(
        "SELECT COUNT(*) AS count FROM favourites"
    ).fetchone()["count"]

    if count > 0:
        print(
            f"favourites already contains {count} rows - skipping."
        )
        return

    place_ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM places ORDER BY id LIMIT 10"
        ).fetchall()
    ]

    if len(place_ids) < 10:
        raise RuntimeError(
            "At least 10 places are required "
            "before seeding favourites."
        )

    notes = [
        "Visit at sunset",
        "Would like to visit again",
        "Good option for the weekend",
        "Recommended for family trip",
        "Interesting place near the CBD",
        "Save for next Sydney trip",
        "Good value option",
        "Popular tourist destination",
        "Recommended dining option",
        "Add to itinerary later",
    ]

    for index in range(10):
        conn.execute(
            """
            INSERT INTO favourites (
                user_id,
                place_id,
                notes
            )
            VALUES (?, ?, ?)
            """,
            (
                index + 1,
                place_ids[index],
                notes[index],
            ),
        )

    conn.commit()

    print("Seeded 10 favourites.")


# ------------------------------------------------------------------
# Recommendations seed
# ------------------------------------------------------------------

def seed_recommendations(conn: sqlite3.Connection) -> None:
    """Insert 10 mock AI recommendation records."""

    count = conn.execute(
        "SELECT COUNT(*) AS count FROM recommendations"
    ).fetchone()["count"]

    if count > 0:
        print(
            f"recommendations already contains "
            f"{count} rows - skipping."
        )
        return

    candidate_places = conn.execute(
        """
        SELECT
            id,
            name,
            category,
            rating,
            price_range
        FROM places
        ORDER BY rating DESC
        """
    ).fetchall()

    if len(candidate_places) < 10:
        raise RuntimeError(
            "At least 10 places are required "
            "before seeding recommendations."
        )

    questions = [
        "Recommend popular attractions in Sydney.",
        "Recommend some cheap restaurants.",
        "Recommend highly rated attractions.",
        "Recommend restaurants in Sydney.",
        "Recommend affordable places to visit.",
        "Recommend highly rated restaurants.",
        "Recommend popular Sydney attractions.",
        "Recommend dining options in Sydney.",
        "Recommend budget-friendly places.",
        "Recommend good places to visit in Sydney.",
    ]

    for index in range(10):
        base_place = candidate_places[index]

        preferences = {
            "category": base_place["category"],
            "budget": 30 if index % 2 == 0 else 50,
            "preference": (
                "popular place"
                if index % 2 == 0
                else "high rating"
            ),
        }

        recommended_places = [
            candidate_places[
                index % len(candidate_places)
            ],
            candidate_places[
                (index + 1) % len(candidate_places)
            ],
            candidate_places[
                (index + 2) % len(candidate_places)
            ],
        ]
        
        recommendation_result = {
            "answer": "Recommended places based on the supplied preferences.",
            "place_ids": [
                place["id"]
                for place in recommended_places
            ],
        }

        conn.execute(
            """
            INSERT INTO recommendations (
                user_id,
                question,
                preferences,
                location,
                recommendation_result
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                index + 1,
                questions[index],
                json.dumps(preferences),
                "Sydney",
                json.dumps(recommendation_result),
            ),
        )

    conn.commit()

    print("Seeded 10 recommendations.")



# ------------------------------------------------------------------
# Initialise database
# ------------------------------------------------------------------

def initialise_database() -> None:
    """Create schema and seed Student 2 data."""

    print(
        f"Initialising Student 2 database: {DB_PATH}"
    )

    conn = get_connection()

    try:
        create_schema(conn)

        seed_places(conn)
        seed_favourites(conn)
        seed_recommendations(conn)

    finally:
        conn.close()

    print(
        "Student 2 database initialisation complete."
    )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    initialise_database()