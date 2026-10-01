"""HTML fragments for the live parts of a Travel Guide (student-4, Aurelia Sari)."""

import json
from html import escape

from services import exchange_rates, weather

CONVERTER_START_AMOUNT = 100


def live_rates_placeholder(destination_id):
    # Loaded after the guide renders, so a slow rates API never delays the page.
    return (
        f"<div id='currency-live' class='fx' hx-get='/api/student-4/guides/{destination_id}/currency/live' "
        "hx-trigger='load' hx-swap='outerHTML'>"
        "<p class='muted fx-note'>Loading live exchange rates...</p></div>"
    )


def _wrap(body):
    return f"<div id='currency-live' class='fx'>{body}</div>"


def _amount(value, code):
    return f"{value:.0f}" if code in exchange_rates.PER_HUNDRED else f"{value:.2f}"


def _converter(data):
    """Two linked amounts. Typing in either side updates the other, and the
    swap button flips which side reads first. The page script converts with
    the rates in data-fx-rates, so no request is made per keystroke."""
    local = data["base"]
    first = next(iter(data["rates"]))
    options = "".join(
        f"<option value='{escape(code)}'{' selected' if code == first else ''}>{escape(code)}</option>"
        for code in data["rates"]
    )
    start_local = CONVERTER_START_AMOUNT / data["rates"][first]
    return (
        f"<div class='fx-converter' data-fx-base='{escape(local)}' "
        f"data-fx-rates='{escape(json.dumps(data['rates']))}'>"
        "<div class='fx-field'>"
        f"<input type='number' min='0' step='any' inputmode='decimal' data-fx-side='foreign' "
        f"value='{CONVERTER_START_AMOUNT}' aria-label='Amount in the selected currency'>"
        f"<select data-fx-currency aria-label='Currency to convert'>{options}</select>"
        "</div>"
        "<button type='button' class='chip fx-swap' data-fx-swap aria-label='Swap conversion direction'>&#8644;</button>"
        "<div class='fx-field'>"
        f"<input type='number' min='0' step='any' inputmode='decimal' data-fx-side='local' "
        f"value='{_amount(start_local, local)}' aria-label='Amount in {escape(local)}'>"
        f"<span class='fx-code'>{escape(local)}</span>"
        "</div>"
        "</div>"
    )


def live_rates_fragment(data):
    lines = "".join(f"<li>{escape(line)}</li>" for line in exchange_rates.rate_lines(data))
    return _wrap(
        "<p class='fx-title'>Live exchange rates</p>"
        f"<ul class='fx-rates'>{lines}</ul>"
        "<p class='fx-title'>Converter</p>"
        + _converter(data)
        + f"<p class='muted fx-note'>{escape(exchange_rates.source_note(data))}</p>"
    )


def live_rates_disabled_fragment():
    return _wrap(
        "<p class='muted fx-note'>Live exchange rates are switched off here "
        "(GUIDES_LIVE_DATA=false), so only the guide tips are shown.</p>"
    )


def live_rates_unavailable_fragment():
    return _wrap(
        "<p class='muted fx-note'>Live exchange rates could not be loaded right now. "
        "The tips above still apply.</p>"
    )


def live_weather_placeholder(destination_id):
    # Loaded after the guide renders, so a slow weather API never delays the page.
    return (
        f"<div id='weather-live' class='wx' hx-get='/api/student-4/guides/{destination_id}/weather/live' "
        "hx-trigger='load' hx-swap='outerHTML'>"
        "<p class='muted wx-note'>Loading current weather...</p></div>"
    )


def _wrap_weather(body):
    return f"<div id='weather-live' class='wx'>{body}</div>"


def live_weather_fragment(data, city):
    now = weather.now_summary(data)
    days = "".join(
        "<li>"
        f"<span class='wx-day'>{escape(day['label'])}</span>"
        f"<span class='wx-cond'>{escape(day['conditions'])}</span>"
        f"<span class='wx-range'>{escape(day['low'])} to {escape(day['high'])}°C</span>"
        f"<span class='muted'>{escape(day['rain'])} mm rain</span>"
        "</li>"
        for day in weather.day_summaries(data)
    )
    return _wrap_weather(
        f"<p class='wx-title'>Now in {escape(city)}</p>"
        "<div class='wx-now'>"
        f"<span class='wx-temp'>{escape(now['temperature'])}°C</span>"
        f"<span class='wx-now__text'><strong>{escape(now['conditions'])}</strong>"
        f"<span class='muted'>Wind {escape(now['wind'])} km/h. {escape(now['rain'])}.</span></span>"
        "</div>"
        f"<p class='wx-title'>Next {len(data['days'])} days</p>"
        f"<ul class='wx-days'>{days}</ul>"
        f"<p class='muted wx-note'>{escape(weather.source_note(data))}</p>"
    )


def live_weather_disabled_fragment():
    return _wrap_weather(
        "<p class='muted wx-note'>Live weather is switched off here "
        "(GUIDES_LIVE_DATA=false), so only typical conditions are shown.</p>"
    )


def live_weather_unavailable_fragment():
    return _wrap_weather(
        "<p class='muted wx-note'>Current weather could not be loaded right now. "
        "The typical conditions below still apply.</p>"
    )
