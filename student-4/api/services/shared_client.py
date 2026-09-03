"""Confirms a valid member session before the AI assistant answers (student-4, Aurelia Sari)."""

import os

import requests

SHARED_API_URL = os.getenv("SHARED_API_URL", "http://shared-api:5000")


def is_authenticated(user_id):
    try:
        response = requests.get(f"{SHARED_API_URL}/access-logs/status/{user_id}", timeout=5)
    except requests.RequestException:
        return False

    if response.status_code != 200:
        return False

    return bool(response.json().get("is_valid"))
