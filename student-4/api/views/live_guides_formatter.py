"""HTML fragments for the live parts of a Travel Guide (student-4, Aurelia Sari)."""

from html import escape

from services import exchange_rates


def live_rates_placeholder(destination_id):
    # Loaded after the guide renders, so a slow rates API never delays the page.
    return (
        f"<div id='currency-live' hx-get='/api/student-4/guides/{destination_id}/currency/live' "
        "hx-trigger='load' hx-swap='outerHTML'>"
        "<p class='muted' style='margin:0.35rem 0 0'>Loading live exchange rates...</p></div>"
    )


def _wrap(body):
    return f"<div id='currency-live' style='margin-top:0.35rem'>{body}</div>"


def live_rates_fragment(data):
    lines = "".join(f"<li>{escape(line)}</li>" for line in exchange_rates.rate_lines(data))
    return _wrap(
        "<p style='margin:0'><strong>Live exchange rates.</strong></p>"
        f"<ul style='margin:0.2rem 0 0; padding-left:1.2rem'>{lines}</ul>"
        f"<p class='muted' style='margin:0.25rem 0 0'>{escape(exchange_rates.source_note(data))}</p>"
    )


def live_rates_disabled_fragment():
    return _wrap(
        "<p class='muted' style='margin:0'>Live exchange rates are switched off here "
        "(GUIDES_LIVE_DATA=false), so only the guide tips are shown.</p>"
    )


def live_rates_unavailable_fragment():
    return _wrap(
        "<p class='muted' style='margin:0'>Live exchange rates could not be loaded right now. "
        "The tips above still apply.</p>"
    )
