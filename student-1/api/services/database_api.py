"""The only place student-1-api talks to student-1-db.

Keeping every call in one module is what makes the data-ownership rule
enforceable: no route reaches around this to touch SQLite.
"""

import os

import requests

DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://student-1-db:5201")
TIMEOUT = 5


def list_trips(params=None):
    response = requests.get(f"{DB_SERVICE_URL}/trips", params=params or {}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_trip(trip_id):
    return requests.get(f"{DB_SERVICE_URL}/trips/{trip_id}", timeout=TIMEOUT)


def create_trip(payload):
    return requests.post(f"{DB_SERVICE_URL}/trips", json=payload, timeout=TIMEOUT)


def update_trip(trip_id, payload):
    return requests.put(f"{DB_SERVICE_URL}/trips/{trip_id}", json=payload, timeout=TIMEOUT)


def delete_trip(trip_id):
    return requests.delete(f"{DB_SERVICE_URL}/trips/{trip_id}", timeout=TIMEOUT)


def list_days(trip_id=None):
    params = {"trip_id": trip_id} if trip_id else {}
    response = requests.get(f"{DB_SERVICE_URL}/days", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_day(day_id):
    return requests.get(f"{DB_SERVICE_URL}/days/{day_id}", timeout=TIMEOUT)


def create_day(payload):
    return requests.post(f"{DB_SERVICE_URL}/days", json=payload, timeout=TIMEOUT)


def update_day(day_id, payload):
    return requests.put(f"{DB_SERVICE_URL}/days/{day_id}", json=payload, timeout=TIMEOUT)


def delete_day(day_id):
    return requests.delete(f"{DB_SERVICE_URL}/days/{day_id}", timeout=TIMEOUT)
