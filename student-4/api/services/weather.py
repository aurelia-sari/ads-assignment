"""Live weather for the Travel Guides weather section (student-4, Aurelia Sari).

Current conditions and a short forecast come from Open-Meteo, which needs no
key. The seeded monthly figures stay on the page as typical conditions. CI
sets GUIDES_LIVE_DATA=false so no test depends on the internet.
"""

import os
import time
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1")
LIVE_DATA_ENABLED = os.getenv("GUIDES_LIVE_DATA", "true").lower() not in ("false", "0", "no")

TIMEOUT = 6

# Open-Meteo refreshes current conditions every 15 minutes.
CACHE_TTL_SECONDS = 30 * 60

# A failed call is not retried for a while, so a slow or broken API does not
# slow down every guide that is opened.
FAILURE_TTL_SECONDS = 5 * 60

FORECAST_DAYS = 3
CURRENT_FIELDS = "temperature_2m,precipitation,weather_code,wind_speed_10m"
DAILY_FIELDS = "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"

# WMO weather interpretation codes, as listed in the Open-Meteo docs.
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with hail",
}

_cache = {}


class LiveDataDisabled(Exception):
    pass


class WeatherUnavailable(Exception):
    pass


def _utc_now():
    return datetime.now(timezone.utc)


def local_month(timezone_name):
    """The month it is in the city right now, not on the server's UTC clock."""
    try:
        zone = ZoneInfo(timezone_name) if timezone_name else timezone.utc
    except (ZoneInfoNotFoundError, ValueError):
        zone = timezone.utc
    return _utc_now().astimezone(zone).strftime("%B")


def describe(code):
    return WEATHER_CODES.get(code, "Mixed conditions")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Open-Meteo returned a non-numeric value: {value!r}")
    return value


def _fetch(destination):
    response = requests.get(
        f"{OPEN_METEO_URL}/forecast",
        params={
            "latitude": destination["latitude"],
            "longitude": destination["longitude"],
            "current": CURRENT_FIELDS,
            "daily": DAILY_FIELDS,
            "forecast_days": FORECAST_DAYS,
            "timezone": "auto",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()

    current = body["current"]
    daily = body["daily"]
    days = []
    for index in range(FORECAST_DAYS):
        days.append({
            "date": date.fromisoformat(daily["time"][index]),
            "high": _number(daily["temperature_2m_max"][index]),
            "low": _number(daily["temperature_2m_min"][index]),
            "precipitation": _number(daily["precipitation_sum"][index]),
            "weather_code": _number(daily["weather_code"][index]),
        })

    return {
        "timezone": body["timezone"],
        "updated": datetime.fromisoformat(current["time"]),
        "current": {
            "temperature": _number(current["temperature_2m"]),
            "precipitation": _number(current["precipitation"]),
            "weather_code": _number(current["weather_code"]),
            "wind_speed": _number(current["wind_speed_10m"]),
        },
        "days": days,
    }


def latest(destination):
    """Current conditions and the next days for one destination row. Serves
    the last good result if a refresh fails, and raises WeatherUnavailable
    only when there is none."""
    if not LIVE_DATA_ENABLED:
        raise LiveDataDisabled("Live guide data is disabled in this environment (GUIDES_LIVE_DATA=false)")
    if destination.get("latitude") is None or destination.get("longitude") is None:
        raise WeatherUnavailable("This destination has no coordinates")

    key = destination["id"]
    now = time.monotonic()
    entry = _cache.get(key, {"data": None, "fetched": 0.0, "failed": None, "error": ""})

    if entry["data"] and now - entry["fetched"] < CACHE_TTL_SECONDS:
        return entry["data"]
    if entry["failed"] is not None and now - entry["failed"] < FAILURE_TTL_SECONDS:
        if entry["data"]:
            return entry["data"]
        raise WeatherUnavailable(entry["error"])

    try:
        data = _fetch(destination)
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
        _cache[key] = {**entry, "failed": now, "error": str(exc)[:200]}
        if entry["data"]:
            return entry["data"]
        raise WeatherUnavailable(str(exc)[:200]) from exc

    _cache[key] = {"data": data, "fetched": now, "failed": None, "error": ""}
    return data


def _degrees(value):
    return str(round(value))


def _millimetres(value):
    return f"{round(value, 1):g}"


def _date(day):
    return f"{day:%a} {day.day} {day:%b}"


def day_label(index, day):
    return ("Today", "Tomorrow")[index] if index < 2 else _date(day)


def now_summary(data):
    current = data["current"]
    rain = current["precipitation"]
    return {
        "temperature": _degrees(current["temperature"]),
        "conditions": describe(current["weather_code"]),
        "wind": f"{round(current['wind_speed']):.0f}",
        # Open-Meteo's current precipitation covers the last 15 minutes.
        "rain": f"{_millimetres(rain)} mm of rain in the last 15 minutes" if rain > 0 else "No rain falling",
    }


def day_summaries(data):
    return [
        {
            "label": day_label(index, day["date"]),
            "date": _date(day["date"]),
            "conditions": describe(day["weather_code"]),
            "low": _degrees(day["low"]),
            "high": _degrees(day["high"]),
            "rain": _millimetres(day["precipitation"]),
        }
        for index, day in enumerate(data["days"])
    ]


def weather_lines(data):
    """Plain lines for the AI Assistant, built from the same rounded values
    the page shows, so the two never disagree."""
    now = now_summary(data)
    lines = [f"Now: {now['temperature']}°C, {now['conditions'].lower()}, wind {now['wind']} km/h. {now['rain']}"]
    for day in day_summaries(data):
        when = day["date"] if day["label"] == day["date"] else f"{day['label']}, {day['date']}"
        lines.append(
            f"{when}: {day['conditions'].lower()}, {day['low']} to {day['high']}°C, "
            f"{day['rain']} mm of rain"
        )
    return lines


def fact_tokens(data):
    now = now_summary(data)
    tokens = [now["temperature"]]
    for day in day_summaries(data):
        tokens += [day["low"], day["high"]]
    return tokens


def source_note(data):
    return (
        f"Current conditions and forecast from Open-Meteo, updated at "
        f"{data['updated']:%H:%M} local time."
    )
