"""Plan step for currency conversions: find the amount and currencies a
question names (student-4, Aurelia Sari).

Conversions are calculated in code from the live rates, never by the model,
so the assistant cannot get the arithmetic wrong.
"""

import re

# Longer names come first and are masked once matched, so "new zealand
# dollar" is never also read as a bare "dollar".
UNSUPPORTED = [
    (r"new zealand dollars?|\bnzd\b", "NZD"),
    (r"singapore dollars?|\bsgd\b", "SGD"),
    (r"canadian dollars?|\bcad\b", "CAD"),
    (r"hong kong dollars?|\bhkd\b", "HKD"),
    (r"taiwan(?:ese)? dollars?|\btwd\b", "TWD"),
    (r"\byuan\b|\brenminbi\b|\brmb\b|\bcny\b", "CNY"),
    (r"\brupiah\b|\bidr\b", "IDR"),
    (r"\bbaht\b|\bthb\b", "THB"),
    (r"\brupees?\b|\binr\b", "INR"),
    (r"\bringgit\b|\bmyr\b", "MYR"),
    (r"korean won|\bkrw\b", "KRW"),
    (r"vietnamese dong|\bvnd\b", "VND"),
    (r"\bpesos?\b|\bphp\b|\bmxn\b", "peso"),
    (r"\bfrancs?\b|\bchf\b", "CHF"),
    (r"\bkron[ae]r?\b|\bsek\b|\bnok\b|\bdkk\b", "krona"),
    (r"\bdirhams?\b|\baed\b", "AED"),
    (r"\briyals?\b|\bsar\b", "SAR"),
]

SUPPORTED = [
    (r"australian dollars?|aussie dollars?|\ba\$|\bau\$|\baud\b", "AUD"),
    (r"u\.?s\.? dollars?|american dollars?|\bus\$|\busd\b", "USD"),
    (r"japanese yen|\byen\b|\bjpy\b|¥", "JPY"),
    (r"\beuros?\b|\beur\b|€", "EUR"),
    (r"british pounds?|\bpounds?\b|\bsterling\b|\bgbp\b|£", "GBP"),
]

BARE_DOLLAR = r"\bdollars?\b|\$"

AMOUNT = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?")

# Wording that asks for a rate even without an amount, such as "how much is a euro worth".
RATE_WORDS = ("rate", "worth", "convert", "conversion", "exchange", "how much", "how many", "equal")


def _find(patterns, text):
    """Returns [(position, label)] and the text with each match blanked out."""
    found = []
    for pattern, label in patterns:
        for match in re.finditer(pattern, text):
            found.append((match.start(), label))
            text = text[:match.start()] + " " * (match.end() - match.start()) + text[match.end():]
    return found, text


def parse(question):
    """Returns None when the question names no currency. Otherwise a dict
    with kind "unsupported", "ambiguous_dollar" or "convert"."""
    lowered = question.lower()

    unsupported, lowered = _find(UNSUPPORTED, lowered)
    supported, lowered = _find(SUPPORTED, lowered)

    if unsupported:
        names = list(dict.fromkeys(label for _, label in sorted(unsupported)))
        return {"kind": "unsupported", "names": names}
    if re.search(BARE_DOLLAR, lowered):
        return {"kind": "ambiguous_dollar"}
    if not supported:
        return None

    amount_match = AMOUNT.search(question)
    amount = None
    if amount_match:
        amount = float(amount_match.group(1).replace(",", "") + (amount_match.group(2) or ""))

    return {
        "kind": "convert",
        "amount": amount,
        "currencies": list(dict.fromkeys(label for _, label in sorted(supported))),
        "asks_rate": any(word in question.lower() for word in RATE_WORDS),
    }
