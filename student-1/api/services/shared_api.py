"""Client for the shared access API.

This is the cross-feature boundary. student-1 stores `traveller_id` on a trip
but does not own traveller records, so it resolves them over HTTP from the
service that does. It never opens shared.db, and it never assumes the shared
service is available.
"""

import os
import time

import requests

SHARED_API_URL = os.getenv("SHARED_API_URL", "http://shared-api:5000")
TIMEOUT = 4

# The trips table re-renders on every filter change, and each render needs the
# same traveller list. A short TTL keeps that to one cross-service call per
# half minute without introducing cache invalidation the team has to reason
# about: stale traveller names for 30 seconds are harmless.
CACHE_TTL_SECONDS = 30

_cache = {"travellers": None, "fetched_at": 0.0}


def get_travellers():
    """Return {traveller_id: traveller}, or {} if the shared service is down."""
    now = time.monotonic()

    if _cache["travellers"] is not None and now - _cache["fetched_at"] < CACHE_TTL_SECONDS:
        return _cache["travellers"]

    try:
        response = requests.get(f"{SHARED_API_URL}/travellers", timeout=TIMEOUT)
        response.raise_for_status()
        travellers = {row["traveller_id"]: row for row in response.json()}
    except (requests.RequestException, ValueError, KeyError):
        # Degrade, do not fail. A trip list is still useful without names, and
        # the shared service being down must not take this feature down too.
        return _cache["travellers"] or {}

    _cache["travellers"] = travellers
    _cache["fetched_at"] = now
    return travellers


def describe_traveller(traveller_id, travellers):
    """Display name for a traveller, falling back to the raw id."""
    traveller = travellers.get(traveller_id)
    if traveller is None:
        return f"#{traveller_id}"
    return traveller["full_name"]
