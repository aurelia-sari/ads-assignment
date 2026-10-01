"""HTML fragments for the live parts of a Travel Guide (student-4, Aurelia Sari)."""

import json
from html import escape

from services import exchange_rates

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
