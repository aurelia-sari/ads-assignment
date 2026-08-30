"""
Normal UI routes for Attractions & Dining. (student-2, Kevin Kim)

Handles HTMX requests for normal database-backed UI functions.
"""

import requests
from flask import Blueprint, request

from services.database_api import (
    create_favourite,
    create_place,
    delete_favourite,
    delete_place,
    get_favourites,
    get_place,
    get_places,
    update_place,
)
from views.html_formatters import (
    error_fragment,
    format_favourites,
    format_place_edit_form,
    format_places,
)


normal_ui_bp = Blueprint("normal_ui", __name__)

DB_DOWN = "Could not reach the Attractions & Dining database service."

# TODO (Kevin Kim): student-4 (Aurelia Sari) owns authentication and does not
# have real user accounts yet. Once student-4 ships auth, replace this with
# the authenticated user's id (e.g. from the session) and filter GET
# /favourites to that user.
CURRENT_USER_ID = "guest"


def place_form_payload():
    return {key: value.strip() for key, value in request.form.items()}


# Places route
@normal_ui_bp.get("/places")
def places():
    places_data = get_places()
    return format_places(places_data)


# Create place
@normal_ui_bp.post("/places")
def create_place_route():
    try:
        response = create_place(place_form_payload())
        if response.status_code == 400:
            return error_fragment(response.json().get("error", "Invalid place.")), 400
        response.raise_for_status()
        return format_places(get_places()), 201
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


# Search a place to edit
@normal_ui_bp.get("/places/edit")
def edit_place_form():
    place_id = request.args.get("id", type=int)
    if place_id is None:
        return error_fragment("Enter a valid Place ID."), 400

    try:
        response = get_place(place_id)
        if response.status_code == 404:
            return error_fragment("Place not found."), 404
        response.raise_for_status()
        return format_place_edit_form(response.json()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


# Update place
@normal_ui_bp.put("/places/<int:place_id>")
def update_place_route(place_id):
    try:
        response = update_place(place_id, place_form_payload())
        if response.status_code == 404:
            return error_fragment("Place not found."), 404
        if response.status_code == 400:
            return error_fragment(response.json().get("error", "Invalid place.")), 400
        response.raise_for_status()
        return format_places(get_places()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


# Delete place
@normal_ui_bp.delete("/places/<int:place_id>")
def delete_place_route(place_id):
    try:
        response = delete_place(place_id)
        if response.status_code == 404:
            return error_fragment("Place not found."), 404
        response.raise_for_status()
        return format_places(get_places()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


# Favourites route
@normal_ui_bp.get("/favourites")
def favourites():
    favourites_data = get_favourites()
    return format_favourites(favourites_data)


# Add favourite
@normal_ui_bp.post("/favourites")
def create_favourite_route():
    place_id = request.values.get("place_id", type=int)
    if place_id is None:
        return error_fragment("place_id is required."), 400

    payload = {
        "user_id": CURRENT_USER_ID,
        "place_id": place_id,
        "notes": (request.values.get("notes", "") or "").strip() or None,
    }

    try:
        response = create_favourite(payload)
        if response.status_code == 404:
            return error_fragment("Place not found."), 404
        if response.status_code == 400:
            return error_fragment(
                response.json().get("error", "Could not add favourite.")
            ), 400
        response.raise_for_status()
        return format_favourites(get_favourites()), 201
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


# Delete favourite
@normal_ui_bp.delete("/favourites/<int:favourite_id>")
def delete_favourite_route(favourite_id):
    try:
        response = delete_favourite(favourite_id)
        if response.status_code == 404:
            return error_fragment("Favourite not found."), 404
        response.raise_for_status()
        return format_favourites(get_favourites()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503