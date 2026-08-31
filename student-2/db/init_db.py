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
            "AHRPTWmq1x_dIvwbRdfEAaWEYBAA60lg1nW81qFDVAQPHMq4yupZN9BGkGb6"
            "klOPnkrcb19Y_FbjNMtDnu5aGEI2n36yLkHxhVmmvhk4X-J1saNdOHdl_H6U"
            "7VOa4RjvC5Yaz9VZpeow=w408-h306-k-no"
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
            "AHRPTWnEu3dPpYCa1Tne3FqySnZRlowQ_AkvvmAR-WxncxI6RyBfUYmnXp2Z"
            "_uPs-m0kK0T14kLp5Arq2YLDprhssGIJsUfzHP5LPdxFPu68nR9WkhInVXbQ"
            "bblHpJz3P17UTiZj7aNJ=w408-h306-k-no"
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
            "AHRPTWmTHimFHUOVaAjKTk5mWxFeekf20d_50eIFQnorJEU2D5NZtlVlnX8U"
            "fJS46_7WjFF0v2RmMs6QbjYZF_cv3ymFXW0pkX_2i20SeuDskEj5gZuDN4hd"
            "NAWNHfmNpHJO_JWancEYUMeimC49=w408-h269-k-no"
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
            "AHRPTWk6SZIANy0T-A5ZmGWE7G0OdfY_myRs2cv_S1pDh312kc5HLqPtJyj"
            "GhQ4CIqa0TZbnULdwqSyk6bE-iybo953tRK4DMIr722CmoAuNSoCf5RkO7Y3"
            "oxbFJrDbFsDFgqz2c7fh7zg=w408-h306-k-no"
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
            "AHRPTWnHTE4e6IHIvJwdbLE2R3NH076vupHFRujWBz9tFKg5fkiXn1vbjiM6"
            "ACxjL9h6BwAqvdaw-A02V1W1Fcc3lrYogbIAtrYvUqjBG7Zb2dpibeO-8UFG"
            "Mm-FEA6mxdmfNLdLrZ5KI-28p0Bs=w408-h306-k-no"
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
            "AHRPTWlDrnTBpUzfZUxTvAejqK9j_lCE1a7hlY1fdGWUVrOmITbS8yH8vHMD"
            "vvPGgNmChWF0jv5FMj-R-DagnQDgKy7mAe0apsFCQ1wydcIBL__TJnGyr76r"
            "_auOBdKcorrTISgoKTte=w408-h306-k-no"
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
            "AHRPTWmfx3P-BV77Tk3GNu-bSZQ26uESjkL3n8F0dhPrR1x7eMSKjgdRCira"
            "kpVnPXLl2xVV9xQqaEiF8o8hHMcgEkgGli7JPUhOoPOxxJaQu42hYeF7End9"
            "kD0pgcS13iXgvbKGkhai=w433-h240-k-no"
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
            "AHRPTWnli0LdsbTDeitDbYE2ThysQtxI8XLiZ7QWASzzSG1y0LUXAXaUyU7f"
            "FZJrtl4Sq-ApFa_wo5NymHH4ZosZc4y1zd9biDbzs7xl3B3S4s6MhjpoCJsl"
            "mvRkflbr1fYpj0h5HbRbbj19bdgB=w408-h306-k-no"
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
            "AHRPTWnqOrhJF0893-3o1d1Qv869y8tD8C5vdKhpWr469cjoSqmwACVmu2h"
            "JkhuDPRm5EnIAF7I6ZLRcpqDp_F-Be2nkdmrTE38DYyUrd3fAhuFYMorWpK"
            "R3nxfEVSCfqRFTJk36S59H=w408-h271-k-no"
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
            "AHRPTWnzK4pPOf_KROAjm4RXy9EXPHosfKVUTMIfi80omjfVFBEgsVLVk8g4"
            "XeFHp223OGAyz6d3etybUM-Qc5L0As0AKbPMMPkR0oelfB8X5W6TURTUBE3"
            "riGWEKUVIooVhp1fcgCWmNA=w408-h306-k-no"
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
            "AHRPTWmgf08oCPnrsiYMYUG2oRuXbjkWrPHh1ycCIw7rT2HxUpTygFYGl_N"
            "h4B2yr47vRNRxxZSm67LttviGZj5KEOt8x5tQ8XXSXyPaWEIZnkFoAqlKVz"
            "_vtZlp9WHRPiBeFStxYM6b=w512-h240-k-no"
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
            "AHRPTWk9NeWt0ilP5Xe8bwpkp4Xm-LzM84APXkZ19kvag1NIuW1H-BoW-s2"
            "KlT0t9NyQPvu70n9v8aKi1BHAwZd8PRWVsX_tSOEs8USHv7D4HBxPs07Bk1"
            "qxA13lL6DwmvCVLxOLHjKJQ2HHes8=w408-h271-k-no"
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
            "AHRPTWnYzpgKPS__G-b6qgXRAdO01t27qi08YwKC7S3uEwlK1gUPfCC0Mk"
            "BuKhGxsxtmpUw_idzeusGsISU4Pb_I1fkUf9XpGsKvX_ghRzHQCjc4FQma"
            "SLVUSnyz1jMBH6jwGY7k71uE6Q=w408-h256-k-no"
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
            "AHRPTWmsuPKzX9osLOWKAhjqWy64jXd8FzvYDIYB4XMzYqK3UYILr72UwV"
            "4_B5IOXanU5db_COmmi1fOD4WWrYtLwo4hOgjoYOjXaeAFZwzu6uU3oTY"
            "C9ZTJqweRaSKcjKfFOUNr3YRv=w408-h285-k-no"
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
            "AHRPTWnwXp5jeHl4EdMZV14GtQ5ytmvYeTgGOZ9FdWoCp2nTTnw9SSBATp"
            "QSGoU3X-UnCwzkbYgDCUX3kcqA_pPfj_eQD1OJN9P4Mck-GhKiHfdardPD"
            "Oc_DvMvQQAvGeqrnAaL-N18=w426-h240-k-no"
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