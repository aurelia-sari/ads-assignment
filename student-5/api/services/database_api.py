"""The only place student-5-api talks to student-5-db.

Keeping every call in one module is what makes the data-ownership rule
enforceable: no route reaches around this to touch SQLite.
"""

import os

import requests

DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://student-5-db:5205")
TIMEOUT = 5


# =========================================================
# Budgets
# =========================================================

def get_budget(trip_id):
    return requests.get(f"{DB_SERVICE_URL}/budgets/{trip_id}", timeout=TIMEOUT)


def create_budget(payload):
    return requests.post(f"{DB_SERVICE_URL}/budgets", json=payload, timeout=TIMEOUT)


def update_budget(trip_id, payload):
    return requests.put(f"{DB_SERVICE_URL}/budgets/{trip_id}", json=payload, timeout=TIMEOUT)


# =========================================================
# Flight / hotel search
# =========================================================

def search_flights(params=None):
    response = requests.get(f"{DB_SERVICE_URL}/flights/search", params=params or {}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def search_hotels(params=None):
    response = requests.get(f"{DB_SERVICE_URL}/hotels/search", params=params or {}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


# =========================================================
# Trip selections
# =========================================================

def list_selections(trip_id):
    response = requests.get(f"{DB_SERVICE_URL}/selections/{trip_id}", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def create_selection(payload):
    return requests.post(f"{DB_SERVICE_URL}/selections", json=payload, timeout=TIMEOUT)


def delete_selection(selection_id):
    return requests.delete(f"{DB_SERVICE_URL}/selections/{selection_id}", timeout=TIMEOUT)


# =========================================================
# Search history
# =========================================================

def list_search_history(trip_id):
    response = requests.get(f"{DB_SERVICE_URL}/search-history/{trip_id}", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def create_search_history(payload):
    return requests.post(f"{DB_SERVICE_URL}/search-history", json=payload, timeout=TIMEOUT)