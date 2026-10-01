"""Live data for the Travel Guides (student-4, Aurelia Sari).

The seeded guide always renders from student-4-db. Live values load
separately and fall back to a clear note, the same way the Release 1 MCP
and RAG routes degrade. HTMX callers always get a 200 fragment, JSON
callers get the real status code.
"""

import requests
from flask import Blueprint, jsonify, request

from services import database_api, exchange_rates, weather
from views.live_guides_formatter import (
    live_rates_disabled_fragment,
    live_rates_fragment,
    live_rates_unavailable_fragment,
    live_weather_disabled_fragment,
    live_weather_fragment,
    live_weather_unavailable_fragment,
)

live_guides_bp = Blueprint("live_guides", __name__)


def _reply(fragment, payload, status):
    if request.headers.get("HX-Request"):
        return fragment, 200
    return jsonify(payload), status


@live_guides_bp.get("/guides/<int:destination_id>/currency/live")
def live_currency(destination_id):
    if not exchange_rates.LIVE_DATA_ENABLED:
        return _reply(
            live_rates_disabled_fragment(),
            {"status": "disabled", "detail": "GUIDES_LIVE_DATA=false"},
            200,
        )

    try:
        response = database_api.get_currency(destination_id)
    except requests.RequestException as exc:
        return _reply(live_rates_unavailable_fragment(), {"status": "unavailable", "detail": str(exc)[:300]}, 503)
    if response.status_code == 404:
        return _reply("", {"status": "not_found"}, 404)
    if response.status_code != 200:
        return _reply(live_rates_unavailable_fragment(), {"status": "unavailable"}, 503)

    try:
        data = exchange_rates.latest(response.json()["currency_code"])
    except exchange_rates.RatesUnavailable as exc:
        return _reply(live_rates_unavailable_fragment(), {"status": "unavailable", "detail": str(exc)}, 503)

    return _reply(
        live_rates_fragment(data),
        {
            "status": "ok",
            "base": data["base"],
            "date": data["date"],
            "fetched_at": data["fetched_at"].isoformat(timespec="seconds"),
            "lines": exchange_rates.rate_lines(data),
        },
        200,
    )


@live_guides_bp.get("/guides/<int:destination_id>/weather/live")
def live_weather(destination_id):
    if not weather.LIVE_DATA_ENABLED:
        return _reply(
            live_weather_disabled_fragment(),
            {"status": "disabled", "detail": "GUIDES_LIVE_DATA=false"},
            200,
        )

    try:
        response = database_api.get_destination(destination_id)
    except requests.RequestException as exc:
        return _reply(live_weather_unavailable_fragment(), {"status": "unavailable", "detail": str(exc)[:300]}, 503)
    if response.status_code == 404:
        return _reply("", {"status": "not_found"}, 404)
    if response.status_code != 200:
        return _reply(live_weather_unavailable_fragment(), {"status": "unavailable"}, 503)

    destination = response.json()
    try:
        data = weather.latest(destination)
    except weather.WeatherUnavailable as exc:
        return _reply(live_weather_unavailable_fragment(), {"status": "unavailable", "detail": str(exc)}, 503)

    return _reply(
        live_weather_fragment(data, destination["city"]),
        {
            "status": "ok",
            "timezone": data["timezone"],
            "updated": data["updated"].isoformat(timespec="minutes"),
            "lines": weather.weather_lines(data),
        },
        200,
    )
