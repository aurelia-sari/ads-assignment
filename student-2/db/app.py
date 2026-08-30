"""
TODO (Kevin Kim): replace the generic `records` resource with the real Attractions & Dining
resources.
"""

"""
Attractions & Dining database API (Student 2 - Kevin Kim).

This service exclusively owns student2.db.
Other backend/API microservices must access the database
through these API endpoints and must not open the SQLite file directly.

Resources:
- places
- favourites
- recommendations
"""

import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE_NAME = "/app/data/student2.db"

# Fields used when creating or updating a place.
PLACE_FIELDS = (
    "external_place_id",
    "name",
    "category",
    "address",
    "latitude",
    "longitude",
    "rating",
    "opening_hours",
    "price_range",
    "description",
    "image_url",
)

PLACE_REQUIRED_FIELDS = ("name", "category", "address")

VALID_CATEGORIES = {"attraction", "restaurant", "activities"}


def validate_place(payload, require_all=True):
    """Return an error message for an invalid place payload, else None."""

    if require_all:
        missing = [
            f for f in PLACE_REQUIRED_FIELDS
            if str(payload.get(f, "")).strip() == ""
        ]
        if missing:
            return f"Missing fields: {', '.join(missing)}"

    category = payload.get("category")
    if category not in (None, "") and category not in VALID_CATEGORIES:
        return f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"

    if payload.get("rating") not in (None, ""):
        try:
            rating = float(payload["rating"])
        except (TypeError, ValueError):
            return "rating must be a number"
        if rating < 0 or rating > 5:
            return "rating must be between 0 and 5"

    if payload.get("price_range") not in (None, ""):
        try:
            price_range = int(payload["price_range"])
        except (TypeError, ValueError):
            return "price_range must be an integer"
        if price_range < 0:
            return "price_range cannot be negative"

    for field in ("latitude", "longitude"):
        if payload.get(field) not in (None, ""):
            try:
                float(payload[field])
            except (TypeError, ValueError):
                return f"{field} must be a number"

    return None


def coerce_place_fields(payload, fields=PLACE_FIELDS):
    """Convert incoming payload values to the types the columns expect."""

    coerced = {}
    for field in fields:
        value = payload.get(field)
        if value in (None, ""):
            coerced[field] = None
        elif field in ("latitude", "longitude", "rating"):
            coerced[field] = float(value)
        elif field == "price_range":
            coerced[field] = int(value)
        else:
            coerced[field] = value
    return coerced


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@app.get("/health")
def health():
    conn = get_db_connection()

    places_count = conn.execute(
        "SELECT COUNT(*) AS n FROM places"
    ).fetchone()["n"]

    favourites_count = conn.execute(
        "SELECT COUNT(*) AS n FROM favourites"
    ).fetchone()["n"]

    recommendations_count = conn.execute(
        "SELECT COUNT(*) AS n FROM recommendations"
    ).fetchone()["n"]

    conn.close()

    return jsonify({
        "service": "student-2-db",
        "status": "running",
        "places": places_count,
        "favourites": favourites_count,
        "recommendations": recommendations_count,
    })

# ===========================
# View
# ===========================

# View places
@app.get("/places")
def get_places():
    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT
            id,
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
        FROM places
        ORDER BY rating DESC, name ASC
        """
    ).fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])


# View a single place
@app.get("/places/<int:place_id>")
def get_place(place_id):
    conn = get_db_connection()

    row = conn.execute(
        "SELECT * FROM places WHERE id = ?", (place_id,)
    ).fetchone()

    conn.close()

    if row is None:
        return jsonify({"error": "Place not found"}), 404

    return jsonify(dict(row))

# View favorites
@app.get("/favourites")
def get_favourites():
    conn = get_db_connection()

    rows = conn.execute(
        f"{FAVOURITE_SELECT} ORDER BY favourites.created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

# View Recommendation
@app.get("/recommendations")
def get_recommendations():
    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM recommendations
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return jsonify([
        dict(row)
        for row in rows
    ])

# View a single recommendation
@app.get("/recommendations/<int:recommendation_id>")
def get_recommendation(recommendation_id):
    conn = get_db_connection()

    row = conn.execute(
        """
        SELECT *
        FROM recommendations
        WHERE id = ?
        """,
        (recommendation_id,),
    ).fetchone()

    conn.close()

    if row is None:
        return jsonify({
            "error": "Recommendation not found"
        }), 404

    return jsonify(dict(row))

# ===========================
# Create / Update / Delete
# ===========================

@app.post("/places")
def create_place():
    payload = request.get_json(silent=True) or {}

    error = validate_place(payload)
    if error:
        return jsonify({"error": error}), 400

    values = coerce_place_fields(payload)

    conn = get_db_connection()
    cursor = conn.execute(
        f"INSERT INTO places ({', '.join(PLACE_FIELDS)}) "
        f"VALUES ({', '.join('?' for _ in PLACE_FIELDS)})",
        tuple(values[f] for f in PLACE_FIELDS),
    )
    conn.commit()
    place_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM places WHERE id = ?", (place_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@app.put("/places/<int:place_id>")
def update_place(place_id):
    payload = request.get_json(silent=True) or {}
    updates = {f: payload[f] for f in PLACE_FIELDS if f in payload}

    if not updates:
        return jsonify({"error": "No updatable fields supplied"}), 400

    error = validate_place(payload, require_all=False)
    if error:
        return jsonify({"error": error}), 400

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT 1 FROM places WHERE id = ?", (place_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return jsonify({"error": "Place not found"}), 404

    values = coerce_place_fields(updates, fields=updates.keys())

    conn.execute(
        f"UPDATE places SET {', '.join(f'{f} = ?' for f in values)} WHERE id = ?",
        (*values.values(), place_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM places WHERE id = ?", (place_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row))


@app.delete("/places/<int:place_id>")
def delete_place(place_id):
    conn = get_db_connection()
    cursor = conn.execute("DELETE FROM places WHERE id = ?", (place_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if not deleted:
        return jsonify({"error": "Place not found"}), 404

    return jsonify({"deleted": place_id})


FAVOURITE_SELECT = """
    SELECT
        favourites.id,
        favourites.user_id,
        favourites.place_id,
        favourites.notes,
        favourites.created_at,
        places.name AS place_name,
        places.category,
        places.address,
        places.rating,
        places.price_range,
        places.image_url
    FROM favourites
    JOIN places
        ON favourites.place_id = places.id
"""

FAVOURITE_REQUIRED_FIELDS = ("user_id", "place_id")


def validate_favourite(payload):
    """Return an error message for an invalid favourite payload, else None."""

    missing = [
        f for f in FAVOURITE_REQUIRED_FIELDS
        if str(payload.get(f, "")).strip() == ""
    ]
    if missing:
        return f"Missing fields: {', '.join(missing)}"

    try:
        int(payload["place_id"])
    except (TypeError, ValueError):
        return "place_id must be an integer"

    return None

# Add favourite
@app.post("/favourites")
def create_favourite():
    payload = request.get_json(silent=True) or {}

    error = validate_favourite(payload)
    if error:
        return jsonify({"error": error}), 400

    user_id = str(payload["user_id"]).strip()
    place_id = int(payload["place_id"])

    conn = get_db_connection()

    place = conn.execute(
        "SELECT 1 FROM places WHERE id = ?", (place_id,)
    ).fetchone()
    if place is None:
        conn.close()
        return jsonify({"error": "Place not found"}), 404

    existing = conn.execute(
        "SELECT 1 FROM favourites WHERE user_id = ? AND place_id = ?",
        (user_id, place_id),
    ).fetchone()
    if existing is not None:
        conn.close()
        return jsonify({"error": "Place is already in favourites for this user"}), 400

    cursor = conn.execute(
        "INSERT INTO favourites (user_id, place_id, notes) VALUES (?, ?, ?)",
        (user_id, place_id, payload.get("notes") or None),
    )
    conn.commit()
    favourite_id = cursor.lastrowid
    row = conn.execute(
        f"{FAVOURITE_SELECT} WHERE favourites.id = ?", (favourite_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


# Delete favourite
@app.delete("/favourites/<int:favourite_id>")
def delete_favourite(favourite_id):
    conn = get_db_connection()
    cursor = conn.execute(
        "DELETE FROM favourites WHERE id = ?", (favourite_id,)
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()

    if not deleted:
        return jsonify({"error": "Favourite not found"}), 404

    return jsonify({"deleted": favourite_id})

# Add recommendation
@app.post("/recommendations")
def create_recommendation():
    payload = request.get_json(silent=True) or {}

    user_id = payload.get("user_id")
    question = payload.get("question")
    preferences = payload.get("preferences")
    location = payload.get("location")
    recommendation_result = payload.get("recommendation_result")

    if not user_id or not question or not recommendation_result:
        return jsonify({
            "error": "user_id, question and recommendation_result are required"
        }), 400

    conn = get_db_connection()

    cursor = conn.execute(
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
            user_id,
            question,
            preferences,
            location,
            recommendation_result,
        ),
    )

    conn.commit()

    recommendation_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "id": recommendation_id
    }), 201

@app.delete("/recommendations/<int:recommendation_id>")
def delete_recommendation(recommendation_id):
    conn = get_db_connection()

    row = conn.execute(
        """
        SELECT id
        FROM recommendations
        WHERE id = ?
        """,
        (recommendation_id,),
    ).fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "Recommendation not found"}), 404

    conn.execute(
        """
        DELETE FROM recommendations
        WHERE id = ?
        """,
        (recommendation_id,),
    )
    conn.commit()
    conn.close()

    return jsonify({"deleted": recommendation_id}), 200




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5202)
