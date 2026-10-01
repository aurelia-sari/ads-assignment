"""Live exchange rates for the Travel Guides currency section (student-4, Aurelia Sari).

Rates come from Frankfurter, which republishes the European Central Bank's
daily reference rates. No key is needed. CI sets GUIDES_LIVE_DATA=false so
no test depends on the internet.
"""

import os
import time
from datetime import datetime, timezone

import requests

FRANKFURTER_URL = os.getenv("FRANKFURTER_URL", "https://api.frankfurter.dev/v1")
LIVE_DATA_ENABLED = os.getenv("GUIDES_LIVE_DATA", "true").lower() not in ("false", "0", "no")

# Frankfurter can take several seconds to answer.
TIMEOUT = 8

# The ECB publishes once per working day, so half a day is fresh enough.
CACHE_TTL_SECONDS = 12 * 60 * 60

# A failed call is not retried for a while, so a slow or broken API does not
# slow down every guide that is opened.
FAILURE_TTL_SECONDS = 5 * 60

TRAVELLER_CURRENCIES = ["USD", "EUR", "GBP"]
OTHER_SEEDED_CURRENCY = {"AUD": "JPY", "JPY": "AUD"}

# Every currency the page shows a rate for, so also every one the AI
# Assistant can convert.
SUPPORTED_CURRENCIES = ["AUD", "JPY", "USD", "EUR", "GBP"]

# Quoted per 100 rather than per 1, since one unit is worth very little.
PER_HUNDRED = {"JPY"}

_cache = {}


class LiveDataDisabled(Exception):
    pass


class RatesUnavailable(Exception):
    pass


def quoted_currencies(local_code):
    others = [OTHER_SEEDED_CURRENCY[local_code]] if local_code in OTHER_SEEDED_CURRENCY else []
    return [code for code in TRAVELLER_CURRENCIES + others if code != local_code]


def _fetch(local_code):
    symbols = quoted_currencies(local_code)
    response = requests.get(
        f"{FRANKFURTER_URL}/latest",
        params={"base": local_code, "symbols": ",".join(symbols)},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()

    rates = {}
    for code in symbols:
        rate = body["rates"][code]
        if not isinstance(rate, (int, float)) or rate <= 0:
            raise ValueError(f"Frankfurter returned an invalid {code} rate: {rate!r}")
        rates[code] = rate

    return {
        "base": local_code,
        "date": body["date"],
        "rates": rates,
        "fetched_at": datetime.now(timezone.utc),
    }


def latest(local_code):
    """Rates for one unit of local_code. Serves the last good result if a
    refresh fails, and raises RatesUnavailable only when there is none."""
    if not LIVE_DATA_ENABLED:
        raise LiveDataDisabled("Live guide data is disabled in this environment (GUIDES_LIVE_DATA=false)")

    now = time.monotonic()
    entry = _cache.get(local_code, {"data": None, "fetched": 0.0, "failed": None, "error": ""})

    if entry["data"] and now - entry["fetched"] < CACHE_TTL_SECONDS:
        return entry["data"]
    if entry["failed"] is not None and now - entry["failed"] < FAILURE_TTL_SECONDS:
        if entry["data"]:
            return entry["data"]
        raise RatesUnavailable(entry["error"])

    try:
        data = _fetch(local_code)
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        _cache[local_code] = {**entry, "failed": now, "error": str(exc)[:200]}
        if entry["data"]:
            return entry["data"]
        raise RatesUnavailable(str(exc)[:200]) from exc

    _cache[local_code] = {"data": data, "fetched": now, "failed": None, "error": ""}
    return data


def rate_lines(data):
    """Lines such as '1 USD = 1.44 AUD'. The page and the AI Assistant both
    use these, so they always quote the same figures."""
    local = data["base"]
    lines = []
    for code, rate in data["rates"].items():
        amount = 100 if code in PER_HUNDRED else 1
        lines.append(f"{amount} {code} = {format_amount(amount / rate, local)} {local}")
    return lines


def format_amount(value, code):
    return f"{value:,.0f}" if code in PER_HUNDRED else f"{value:,.2f}"


def convert(amount, from_code, to_code):
    """Returns (converted, rate, data) using the same cached rates as the
    page. A seeded currency is used as the base, since its cached rates
    cover every other supported currency."""
    base = next((code for code in (from_code, to_code) if code in OTHER_SEEDED_CURRENCY), "AUD")
    data = latest(base)

    def per_base(code):
        return 1.0 if code == base else data["rates"][code]

    rate = per_base(to_code) / per_base(from_code)
    return amount * rate, rate, data


def source_note(data):
    published = datetime.strptime(data["date"], "%Y-%m-%d")
    fetched = data["fetched_at"]
    return (
        f"European Central Bank reference rates via Frankfurter, published "
        f"{published.day} {published:%B %Y} and fetched at {fetched:%H:%M} UTC. "
        "Banks and exchange counters add their own margin."
    )
