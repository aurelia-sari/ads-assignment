"""Trip CRUD routes. Every response is an HTMX fragment, not JSON."""

import requests
from flask import Blueprint, request

from services import database_api, shared_api
from views.formatters import error_fragment, trip_form, trips_table

trips_bp = Blueprint("trips", __name__)

DB_DOWN = "Could not reach the trips database service."


@trips_bp.get("/health")
def health():
    return {"service": "student-1-api", "status": "running"}


@trips_bp.get("/trips")
def list_trips():
    params = {
        "destination": request.args.get("destination", "").strip(),
        "status": request.args.get("status", "").strip(),
    }
    try:
        trips = database_api.list_trips(params)
        # Cross-feature read: traveller records belong to the shared access
        # service, so they are fetched over HTTP rather than joined in SQL.
        return trips_table(trips, shared_api.get_travellers()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@trips_bp.get("/trips/new")
def new_trip_form():
    return trip_form(travellers=shared_api.get_travellers()), 200


@trips_bp.get("/trips/<int:trip_id>/edit")
def edit_trip_form(trip_id):
    try:
        response = database_api.get_trip(trip_id)
        if response.status_code == 404:
            return error_fragment("Trip not found."), 404
        response.raise_for_status()
        return trip_form(response.json(), shared_api.get_travellers()), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


def form_payload():
    payload = {key: value.strip() for key, value in request.form.items()}
    for numeric in ("traveller_id", "budget_aud"):
        if payload.get(numeric):
            payload[numeric] = float(payload[numeric])
    return payload


def refreshed_table():
    return trips_table(database_api.list_trips(), shared_api.get_travellers())


@trips_bp.post("/trips")
def create_trip():
    try:
        response = database_api.create_trip(form_payload())
        if response.status_code == 400:
            return error_fragment(response.json().get("error", "Invalid trip.")), 400
        response.raise_for_status()
        return refreshed_table(), 201
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@trips_bp.put("/trips/<int:trip_id>")
def update_trip(trip_id):
    try:
        response = database_api.update_trip(trip_id, form_payload())
        if response.status_code == 404:
            return error_fragment("Trip not found."), 404
        if response.status_code == 400:
            return error_fragment(response.json().get("error", "Invalid trip.")), 400
        response.raise_for_status()
        return refreshed_table(), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503


@trips_bp.delete("/trips/<int:trip_id>")
def delete_trip(trip_id):
    try:
        response = database_api.delete_trip(trip_id)
        if response.status_code == 404:
            return error_fragment("Trip not found."), 404
        response.raise_for_status()
        return refreshed_table(), 200
    except requests.RequestException as exc:
        return error_fragment(DB_DOWN, exc), 503
