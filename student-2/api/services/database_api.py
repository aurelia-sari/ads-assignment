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

# View favorites
def get_favourites():
    """Fetch all favourites from the database service."""

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/favourites"
    )
    response.raise_for_status()

    return response.json()