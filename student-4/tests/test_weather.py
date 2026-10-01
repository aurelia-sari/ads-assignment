"""Unit tests for the live weather in the Travel Guides weather section.

Open-Meteo and student-4-db are stubbed, so these need no network and run
in CI where GUIDES_LIVE_DATA is false.

    python -m pytest student-4/tests/test_weather.py
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app import app  # noqa: E402
from agentic_loop.core.validator import validate_answer  # noqa: E402
from agentic_loop.pipelines.guide_chat_pipeline import gather_guide_facts  # noqa: E402
from services import weather  # noqa: E402

HTMX = {"HX-Request": "true"}

DESTINATIONS = {
    1: {"id": 1, "country": "Australia", "city": "Sydney", "region": "New South Wales",
        "latitude": -33.8688, "longitude": 151.2093, "timezone": "Australia/Sydney"},
    4: {"id": 4, "country": "Australia", "city": "Perth", "region": "Western Australia",
        "latitude": -31.9523, "longitude": 115.8613, "timezone": "Australia/Perth"},
}
MONTHS = [
    {"month": "September", "avg_temp": 20, "rainfall": 68, "best_visit_time": "Spring is mild."},
    {"month": "October", "avg_temp": 22, "rainfall": 77, "best_visit_time": "Warm and dry."},
]

# Trimmed from a real Open-Meteo reply for Sydney on 2 October 2026.
SYDNEY_FORECAST = {
    "timezone": "Australia/Sydney",
    "current": {"time": "2026-10-02T00:00", "temperature_2m": 19.1, "precipitation": 0.0,
                "weather_code": 1, "wind_speed_10m": 10.4},
    "daily": {"time": ["2026-10-02", "2026-10-03", "2026-10-04"],
              "temperature_2m_max": [23.3, 20.5, 23.0],
              "temperature_2m_min": [16.3, 14.9, 13.8],
              "precipitation_sum": [1.5, 25.9, 0.0],
              "weather_code": [53, 95, 2]},
}

# 01:00 on 1 October in Sydney, still 23:00 on 30 September in Perth.
END_OF_SEPTEMBER_UTC = datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


def without(key, section=None):
    if section is None:
        return {name: value for name, value in SYDNEY_FORECAST.items() if name != key}
    return {**SYDNEY_FORECAST, section: {name: value for name, value in SYDNEY_FORECAST[section].items()
                                         if name != key}}


def replaced(section, **fields):
    return {**SYDNEY_FORECAST, section: {**SYDNEY_FORECAST[section], **fields}}


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    weather._cache.clear()
    monkeypatch.setattr(weather, "LIVE_DATA_ENABLED", True)
    monkeypatch.setattr(weather, "_utc_now", lambda: END_OF_SEPTEMBER_UTC)


@pytest.fixture
def open_meteo_calls(monkeypatch):
    """Stubs both student-4-db and Open-Meteo. Set calls.reply to change
    what Open-Meteo returns. Every Open-Meteo call is recorded."""

    class Calls(list):
        reply = None

    calls = Calls()

    def fake_get(url, params=None, **kwargs):
        if "open-meteo" in url:
            calls.append(params)
            if isinstance(calls.reply, Exception):
                raise calls.reply
            return calls.reply if calls.reply is not None else FakeResponse(SYDNEY_FORECAST)
        last = url.rstrip("/").split("/")[-1]
        if last == "weather":
            return FakeResponse(MONTHS)
        if last.isdigit() and int(last) in DESTINATIONS:
            return FakeResponse(DESTINATIONS[int(last)])
        return FakeResponse({"error": "not found"}, 404)

    monkeypatch.setattr(requests, "get", fake_get)
    return calls


# Live

def test_live_weather_shows_now_and_the_next_three_days(client, open_meteo_calls):
    html = client.get("/guides/1/weather/live", headers=HTMX).get_data(as_text=True)
    assert "Now in Sydney" in html
    assert "19°C" in html
    assert "Mainly clear" in html
    assert "Wind 10 km/h. No rain falling." in html
    assert "<span class='wx-day'>Today</span><span class='wx-cond'>Drizzle</span>" in html
    assert "<span class='wx-day'>Tomorrow</span><span class='wx-cond'>Thunderstorm</span>" in html
    assert "<span class='wx-day'>Sun 4 Oct</span>" in html
    assert "16 to 23°C" in html
    assert "25.9 mm rain" in html
    assert "updated at 00:00 local time" in html
    assert open_meteo_calls[0]["latitude"] == -33.8688
    assert open_meteo_calls[0]["timezone"] == "auto"
    assert open_meteo_calls[0]["forecast_days"] == 3


def test_json_callers_get_the_same_lines_as_the_ai(client, open_meteo_calls):
    body = client.get("/guides/1/weather/live").get_json()
    assert body["status"] == "ok"
    assert body["timezone"] == "Australia/Sydney"
    assert body["updated"] == "2026-10-02T00:00"
    assert body["lines"] == [
        "Now: 19°C, mainly clear, wind 10 km/h. No rain falling",
        "Today, Fri 2 Oct: drizzle, 16 to 23°C, 1.5 mm of rain",
        "Tomorrow, Sat 3 Oct: thunderstorm, 15 to 20°C, 25.9 mm of rain",
        "Sun 4 Oct: partly cloudy, 14 to 23°C, 0 mm of rain",
    ]


def test_detail_page_loads_live_weather_after_rendering(client, monkeypatch):
    def fake_get(url, **kwargs):
        if "open-meteo" in url:
            raise AssertionError("the guide page must not wait for the weather API")
        if url.endswith("/destinations/1"):
            return FakeResponse(DESTINATIONS[1])
        if url.endswith("/weather"):
            return FakeResponse(MONTHS)
        return FakeResponse([] if not url.endswith(("/safety", "/currency")) else None, 404)

    monkeypatch.setattr(requests, "get", fake_get)
    html = client.get("/guides/1").get_data(as_text=True)
    assert "hx-get='/api/student-4/guides/1/weather/live'" in html
    assert "hx-target='#weather-months'" in html


def test_month_tab_swaps_only_the_typical_conditions(client, open_meteo_calls):
    html = client.get("/guides/1/weather?month=September").get_data(as_text=True)
    assert html.startswith("<div id='weather-months'>")
    assert "average daytime high in September" in html
    assert "weather/live" not in html
    assert open_meteo_calls == []


# The city's own month

def test_local_month_follows_the_city_not_the_server():
    assert weather.local_month("Australia/Sydney") == "October"
    assert weather.local_month("Australia/Perth") == "September"
    assert weather.local_month("Asia/Tokyo") == "October"
    assert weather.local_month(None) == "September"
    assert weather.local_month("Not/AZone") == "September"


@pytest.mark.parametrize("destination_id, month", [(1, "Oct"), (4, "Sep")])
def test_detail_page_opens_on_the_city_month(client, open_meteo_calls, destination_id, month):
    html = client.get(f"/guides/{destination_id}").get_data(as_text=True)
    active = re.findall(r"class='chip is-active'[^>]*hx-target='#weather-months'[^>]*>(\w+)</button>", html)
    assert active == [month]


def test_unseeded_month_falls_back_to_the_city_month(client, open_meteo_calls):
    html = client.get("/guides/1/weather?month=Notamonth").get_data(as_text=True)
    assert "average daytime high in October" in html


# Disabled, as in CI

def test_disabled_makes_no_network_call(client, monkeypatch):
    monkeypatch.setattr(weather, "LIVE_DATA_ENABLED", False)

    def refuse(*args, **kwargs):
        raise AssertionError("disabled live data must not make a network call")

    monkeypatch.setattr(requests, "get", refuse)

    response = client.get("/guides/1/weather/live")
    assert response.status_code == 200
    assert response.get_json()["status"] == "disabled"

    html = client.get("/guides/1/weather/live", headers=HTMX).get_data(as_text=True)
    assert "switched off" in html


# Timeout and bad responses

def test_timeout_falls_back_to_a_clear_note(client, open_meteo_calls):
    open_meteo_calls.reply = requests.Timeout("read timed out")

    response = client.get("/guides/1/weather/live")
    assert response.status_code == 503
    assert response.get_json()["status"] == "unavailable"

    response = client.get("/guides/1/weather/live", headers=HTMX)
    assert response.status_code == 200
    assert "typical conditions below still apply" in response.get_data(as_text=True)


@pytest.mark.parametrize("reply", [
    FakeResponse({"reason": "Latitude must be in range"}, 400),
    FakeResponse(ValueError("not JSON")),
    FakeResponse(without("current")),
    FakeResponse(without("temperature_2m", "current")),
    FakeResponse(replaced("current", temperature_2m=None)),
    FakeResponse(replaced("daily", time=["2026-10-02"])),
], ids=["http-error", "not-json", "no-current", "missing-field", "null-value", "short-forecast"])
def test_bad_response_falls_back_to_a_clear_note(client, open_meteo_calls, reply):
    open_meteo_calls.reply = reply
    response = client.get("/guides/1/weather/live")
    assert response.status_code == 503
    assert response.get_json()["status"] == "unavailable"


def test_unknown_destination_returns_not_found(client, open_meteo_calls):
    assert client.get("/guides/999/weather/live").status_code == 404
    assert open_meteo_calls == []


def test_destination_without_coordinates_is_unavailable(open_meteo_calls):
    with pytest.raises(weather.WeatherUnavailable):
        weather.latest({**DESTINATIONS[1], "latitude": None})
    assert open_meteo_calls == []


# Cache

def test_weather_is_cached(client, open_meteo_calls):
    client.get("/guides/1/weather/live")
    client.get("/guides/1/weather/live")
    assert len(open_meteo_calls) == 1


def test_expired_weather_is_refreshed(client, open_meteo_calls, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(weather.time, "monotonic", lambda: clock[0])
    client.get("/guides/1/weather/live")
    clock[0] += weather.CACHE_TTL_SECONDS + 1
    client.get("/guides/1/weather/live")
    assert len(open_meteo_calls) == 2


def test_last_good_weather_is_kept_when_a_refresh_fails(client, open_meteo_calls, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(weather.time, "monotonic", lambda: clock[0])
    client.get("/guides/1/weather/live")

    clock[0] += weather.CACHE_TTL_SECONDS + 1
    open_meteo_calls.reply = requests.ConnectionError("refused")
    body = client.get("/guides/1/weather/live").get_json()
    assert body["status"] == "ok"
    assert body["updated"] == "2026-10-02T00:00"


def test_a_failed_call_is_not_retried_straight_away(client, open_meteo_calls):
    open_meteo_calls.reply = requests.Timeout("read timed out")
    client.get("/guides/1/weather/live")
    client.get("/guides/1/weather/live")
    assert len(open_meteo_calls) == 1


# Weather codes

@pytest.mark.parametrize("code, label", [
    (0, "Clear sky"), (3, "Overcast"), (45, "Fog"), (63, "Rain"), (75, "Heavy snow"),
    (81, "Showers"), (95, "Thunderstorm"), (42, "Mixed conditions"),
])
def test_weather_codes_get_short_plain_labels(code, label):
    assert weather.describe(code) == label


# AI Assistant grounding

def test_ai_uses_the_same_weather_as_the_page(open_meteo_calls):
    context, fact_tokens, has_data = gather_guide_facts("weather", 1)
    assert has_data
    assert "It is currently October there." in context
    assert "- Now: 19°C, mainly clear, wind 10 km/h. No rain falling" in context
    assert "- Tomorrow, Sat 3 Oct: thunderstorm, 15 to 20°C, 25.9 mm of rain" in context
    assert "not a forecast" in context
    assert {"19", "16", "23"} <= set(fact_tokens)
    assert validate_answer("It is 19°C and mainly clear in Sydney right now.", fact_tokens)["valid"]


def test_ai_is_told_not_to_describe_current_weather_when_none_is_available(open_meteo_calls):
    open_meteo_calls.reply = requests.Timeout("read timed out")
    context, fact_tokens, has_data = gather_guide_facts("weather", 1)
    assert has_data
    assert "do not describe current conditions or a forecast" in context
    assert "Now:" not in context
    assert fact_tokens == ["20", "22", "68", "77"]
