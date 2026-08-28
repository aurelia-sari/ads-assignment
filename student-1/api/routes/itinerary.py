"""Day-by-day itinerary CRUD routes."""

import requests
from flask import Blueprint, request

from services import database_api
from views.formatters import day_form, days_table, error_fragment

itinerary_bp = Blueprint("itinerary", __name__)

DB_DOWN = "Could not reach the trips database service."


def days_for_trip(trip_id):
    trip_response = database_api.get_trip(trip_id)
    trip = trip_response.json() if trip_response.status_code == 200 else None
    return days_table(database_api.list_days(trip_id), trip)


@itinerary_bp.get("/trips/<int:trip_id>/days")
def list_trip_days(trip_id):
    try:
        return days_for_trip(trip_id), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@itinerary_bp.get("/days")
def list_all_days():
    try:
        return days_table(database_api.list_days()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@itinerary_bp.post("/days")
def create_day():
    payload = {key: value.strip() for key, value in request.form.items()}
    trip_id = payload.get("trip_id")

    if not trip_id:
        return error_fragment("Select a trip before adding an itinerary day."), 400

    try:
        response = database_api.create_day(payload)
        if response.status_code in (400, 404):
            return error_fragment(response.json().get("error", "Invalid itinerary day.")), response.status_code
        response.raise_for_status()
        return days_for_trip(int(trip_id)), 201
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@itinerary_bp.get("/days/<int:day_id>/edit")
def edit_day_form(day_id):
    try:
        response = database_api.get_day(day_id)
        if response.status_code == 404:
            return error_fragment("Itinerary day not found."), 404
        response.raise_for_status()
        return day_form(response.json()["trip_id"], response.json()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@itinerary_bp.put("/days/<int:day_id>")
def update_day(day_id):
    payload = {key: value.strip() for key, value in request.form.items()}

    try:
        response = database_api.update_day(day_id, payload)
        if response.status_code == 404:
            return error_fragment("Itinerary day not found."), 404
        if response.status_code == 400:
            return error_fragment(response.json().get("error", "Invalid day.")), 400
        response.raise_for_status()
        return days_for_trip(response.json()["trip_id"]), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@itinerary_bp.delete("/days/<int:day_id>")
def delete_day(day_id):
    try:
        existing = database_api.get_day(day_id)
        trip_id = existing.json().get("trip_id") if existing.status_code == 200 else None

        response = database_api.delete_day(day_id)
        if response.status_code == 404:
            return error_fragment("Itinerary day not found."), 404
        response.raise_for_status()

        if trip_id:
            return days_for_trip(trip_id), 200
        return days_table(database_api.list_days()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503
