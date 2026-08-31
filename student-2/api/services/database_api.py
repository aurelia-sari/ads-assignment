"""
Database API client for (student-2, Kevin Kim).

This module communicates with the Student 2 database microservice.
The backend must not access SQLite directly.
"""

import os
import requests


DATABASE_SERVICE_URL = os.environ.get(
    "DATABASE_SERVICE_URL",
    "http://student-2-db:5202"
)

# View places
def get_places():
    """Fetch all places from the database service."""

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/places"
    )
    response.raise_for_status()

    return response.json()

# View a single place
def get_place(place_id):
    """Fetch a single place from the database service."""

    return requests.get(
        f"{DATABASE_SERVICE_URL}/places/{place_id}"
    )


# Create place
def create_place(payload):
    """Create a place through the database service."""

    return requests.post(
        f"{DATABASE_SERVICE_URL}/places",
        json=payload,
    )


# Update place
def update_place(place_id, payload):
    """Update a place through the database service."""

    return requests.put(
        f"{DATABASE_SERVICE_URL}/places/{place_id}",
        json=payload,
    )


# Delete place
def delete_place(place_id):
    """Delete a place through the database service."""

    return requests.delete(
        f"{DATABASE_SERVICE_URL}/places/{place_id}"
    )

# View favorites
def get_favourites(user_id=None):
    """Fetch favourites from the database service."""

    params = {}

    if user_id is not None:
        params["user_id"] = user_id

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/favourites",
        params=params,
    )

    response.raise_for_status()

    return response.json()


# Add favourite
def create_favourite(payload):
    """Create a favourite through the database service."""

    return requests.post(
        f"{DATABASE_SERVICE_URL}/favourites",
        json=payload,
    )


# Delete favourite
def delete_favourite(favourite_id, user_id):
    return requests.delete(
        f"{DATABASE_SERVICE_URL}/favourites/{favourite_id}",
        json={
            "user_id": user_id
        },
        timeout=5,
    )

# View recommendation
def get_recommendations():
    response = requests.get(
        f"{DATABASE_SERVICE_URL}/recommendations",
        timeout=10,
    )
    response.raise_for_status()
    return response.json()

# View a single recommendation
def get_recommendation(recommendation_id):
    """Fetch a single recommendation from the database service."""

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/recommendations/{recommendation_id}",
        timeout=10,
    )
    return response

# Add recommendation    
def create_recommendation(payload):
    return requests.post(
        f"{DATABASE_SERVICE_URL}/recommendations",
        json=payload,
        timeout=10,
    )

# Delete recommendation
def delete_recommendation(recommendation_id):
    """Delete a recommendation through the database service."""

    return requests.delete(
        f"{DATABASE_SERVICE_URL}/recommendations/{recommendation_id}",
        timeout=10,
    )