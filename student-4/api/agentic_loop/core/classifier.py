"""Plan step: classify a guide-chat question into an intent category
(student-4, Aurelia Sari). Categories: currency, weather, visa, transport,
safety, unrelated, or other:<feature_name>.
"""

GUIDE_CATEGORY_KEYWORDS = {
    "currency": ["currency", "money", "exchange rate", "cash", "aud", "dollar", "afford", "cost of"],
    "weather": ["weather", "temperature", "rain", "rainfall", "climate", "forecast", "season", "hot", "cold"],
    "visa": ["visa", "passport", "entry requirement", "nationality", "immigration", "enter the country"],
    "transport": ["transport", "metro", "train", "taxi", "rental", "getting around", "public transport", "flight"],
    "safety": ["safety", "safe", "crime", "danger", "precaution", "risk"],
}


def classify_intent(question, redirect_map):
    """Returns (intent, redirect_row). redirect_row is set only for other:<feature_name>."""
    # Checked first: "book a flight" is another feature's job even though
    # "flight" alone is this feature's own transport guide topic.
    lowered = question.lower()

    for row in redirect_map:
        if row["keyword"] in lowered:
            return f"other:{row['feature_name']}", row

    for category, keywords in GUIDE_CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category, None

    return "unrelated", None


def extract_destination(question, destinations):
    """Finds which destination a question is about by matching its city
    name, so the assistant does not depend on a separately picked city.
    """
    lowered = question.lower()
    matches = [d for d in destinations if d["city"].lower() in lowered]
    if not matches:
        return None
    return max(matches, key=lambda d: len(d["city"]))
