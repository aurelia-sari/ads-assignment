"""Create and seed the Attractions & Dining database (student-2, Kevin Kim).

TODO (Kevin Kim): replace `records` with the real schema for Attractions & Dining.
The project specification requires at least ten records per table, so keep the
seed at ten or more when you change it.
"""

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

WIKIMEDIA = (
    "https://commons.wikimedia.org/wiki/"
    "Special:FilePath/{}?width=400"
)


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
        "image_url": WIKIMEDIA.format(
            "Sydney_Opera_House%2C_2017_%2801%29.jpg"
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
        "image_url": WIKIMEDIA.format(
            "Sydney_Harbour_Bridge.jpg"
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
        "image_url": WIKIMEDIA.format(
            "Wallaby_at_Taronga_Zoo%2C_2016.jpg"
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
        "image_url": WIKIMEDIA.format(
            "Gates_at_Royal_Botanic_Gardens_"
            "viewed_from_Art_Gallery_Road.jpg"
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
        "image_url": WIKIMEDIA.format(
            "Bondi_from_above.jpg"
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
        "image_url": WIKIMEDIA.format(
            "Sydney_%28AU%29%2C_The_Rocks_--_2019_--_2133.jpg"
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
        "image_url": WIKIMEDIA.format(
            "Summer_days_at_Manly_Beach.jpg"
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
        "image_url": WIKIMEDIA.format(
            "Art_Gallery_of_New_South_Wales%2C_2022%2C_09.jpg"
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
        "image_url": (
            "https://picsum.photos/seed/"
            "harrys-cafe-de-wheels/400/240"
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
        "image_url": (
            "https://picsum.photos/seed/"
            "chat-thai-haymarket/400/240"
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
        "image_url": (
            "https://picsum.photos/seed/mamak/400/240"
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
        "image_url": (
            "https://picsum.photos/seed/"
            "the-grounds-of-alexandria/400/240"
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
        "image_url": (
            "https://picsum.photos/seed/mr-wong/400/240"
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
        "image_url": (
            "https://picsum.photos/seed/"
            "bourke-street-bakery/400/240"
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
        "image_url": (
            "https://picsum.photos/seed/"
            "gelato-messina-darlinghurst/400/240"
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
            user_id TEXT NOT NULL,
            place_id INTEGER NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (place_id)
                REFERENCES places(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            preferences TEXT,
            location TEXT,
            recommendation_result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Temporary compatibility table for shared smoke_test.py.
        CREATE TABLE IF NOT EXISTS records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            created_on TEXT NOT NULL
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
                f"user-{(index % 3) + 1}",
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

        recommendations = [
            {
                "place_id": place["id"],
                "place_name": place["name"],
                "reason": (
                    "Recommended based on "
                    "the supplied preferences."
                ),
            }
            for place in recommended_places
        ]

        recommendation_result = {
            "recommendations": recommendations
        }

        conn.execute(
            """
            INSERT INTO recommendations (
                user_id,
                preferences,
                location,
                recommendation_result
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                f"user-{(index % 3) + 1}",
                json.dumps(preferences),
                "Sydney",
                json.dumps(recommendation_result),
            ),
        )

    conn.commit()

    print("Seeded 10 recommendations.")


# ------------------------------------------------------------------
# Temporary smoke-test compatibility seed
# ------------------------------------------------------------------

def seed_records(conn: sqlite3.Connection) -> None:
    """Seed temporary generic records for shared CI smoke testing."""

    count = conn.execute(
        "SELECT COUNT(*) AS count FROM records"
    ).fetchone()["count"]

    if count > 0:
        print(
            f"records already contains {count} rows - skipping."
        )
        return

    records = [
        (
            f"Attractions & Dining record {index}",
            (
                "attraction"
                if index <= 6
                else "restaurant"
            ),
            (
                "Temporary smoke test compatibility "
                f"record {index}"
            ),
            f"2026-08-{index:02d}",
        )
        for index in range(1, 13)
    ]

    conn.executemany(
        """
        INSERT INTO records (
            title,
            category,
            detail,
            created_on
        )
        VALUES (?, ?, ?, ?)
        """,
        records,
    )

    conn.commit()

    print(
        f"Seeded {len(records)} temporary records."
    )


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

        # Temporary compatibility data for shared smoke_test.py.
        seed_records(conn)

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