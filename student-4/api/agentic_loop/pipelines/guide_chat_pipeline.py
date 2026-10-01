"""Act step: assemble grounded context for one guide category and ask the
model (student-4, Aurelia Sari).
"""

import re

from agentic_loop.collectors import guide_collector
from agentic_loop.core.validator import figures_in
from services import exchange_rates, weather
from services.ai_client import ask_ai
from services.prompt_loader import load_prompt

GUIDE_SOURCE_PATH = "/student-4/#guides"

# Claims about paying that the model has made against the guide, such as
# "you do not need cash in Sydney" or "cards work almost everywhere in Kyoto".
NO_CASH_NEEDED = re.compile(
    r"\b(do not|don't|won't|will not|never) (really |usually |generally )?need (any |to carry )?cash"
    r"|\bno need (for|to carry) cash|\bcashless|\bcash is not (needed|necessary)",
    re.IGNORECASE,
)
CARDS_EVERYWHERE = re.compile(
    r"\bcards? (are|is) (accepted|taken) (almost |nearly |pretty much )?everywhere"
    r"|\bcards? works? (almost |nearly |pretty much )?everywhere"
    r"|\bpay(ing)? by card (almost |nearly |pretty much )?everywhere",
    re.IGNORECASE,
)
GUIDE_SAYS_CARRY_CASH = re.compile(r"carry (a little |some )?cash|cash is (still )?common", re.IGNORECASE)
GUIDE_SAYS_CARDS_EVERYWHERE = re.compile(r"cards are accepted almost everywhere", re.IGNORECASE)


def currency_checks(context):
    """Stricter checks for a currency answer, read from the same context the
    model was given. It must not contradict the guide's payment advice, and
    must not quote a figure, such as a rate, that the context does not hold."""
    forbidden = []
    if GUIDE_SAYS_CARRY_CASH.search(context):
        forbidden.append(NO_CASH_NEEDED)
    if not GUIDE_SAYS_CARDS_EVERYWHERE.search(context):
        forbidden.append(CARDS_EVERYWHERE)
    return {"forbidden": forbidden, "known_figures": figures_in(context)}


MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
# "May" counts only after words like "in", since it is also a verb.
MONTH_NAMED = re.compile(
    r"\b(january|jan|february|feb|march|mar|april|apr|june|jun|july|jul|august|aug"
    r"|september|sept|sep|october|oct|november|nov|december|dec)\b"
    r"|\b(?:in|during|for|of|early|late|mid)\s+(may)\b",
    re.IGNORECASE,
)
MONTH_LINE = re.compile(r"^- (\w+): average daytime high")


def months_named(question):
    named = set()
    for match in MONTH_NAMED.finditer(question):
        prefix = (match.group(1) or match.group(2)).lower()
        named.add(next(month for month in MONTHS if month.lower().startswith(prefix)))
    return named


def weather_checks(question, context):
    """When the question names a month, the answer may only quote that
    month's figures or the live weather, not another month's, as in August
    being given July's rainfall."""
    named = months_named(question)
    if not named:
        return {}
    allowed = [
        line for line in context.splitlines()
        if not (MONTH_LINE.match(line) and MONTH_LINE.match(line).group(1) not in named)
    ]
    return {"known_figures": figures_in("\n".join(allowed))}


def guide_fallback(intent, question, destination):
    """The guide's own text for a question the model failed twice. Returns
    None when there is no short exact answer to quote."""
    text = None
    if intent == "currency":
        info = guide_collector.collect_currency(destination["id"])
        text = info and info["exchange_tips"]
    elif intent == "weather":
        named = months_named(question)
        text = " ".join(
            f"The average daytime high in {item['month']} is about {item['avg_temp']:g}°C, "
            f"with around {item['rainfall']:g}mm of rainfall."
            for item in guide_collector.collect_weather(destination["id"])
            if item["month"] in named
        )
    if not text:
        return None
    return f"Here is what the guide says for {destination['city']}, {destination['country']}. {text}"


def _weather_active_month(items, timezone_name):
    current_month = weather.local_month(timezone_name)
    matching = [item for item in items if item["month"] == current_month]
    if matching:
        return matching[0]
    return items[0] if items else None


def _live_weather_facts(destination):
    """Uses the same cached forecast and rounding as the guide page, so the
    assistant and the page never quote different conditions."""
    try:
        data = weather.latest(destination) if destination else None
    except (weather.LiveDataDisabled, weather.WeatherUnavailable):
        data = None
    if data is None:
        return (
            "Live weather is not available right now, so do not describe current "
            "conditions or a forecast. Only the typical monthly figures apply."
        ), []

    context = (
        "Live weather:\n"
        + "\n".join(f"- {line}" for line in weather.weather_lines(data))
        + f"\n{weather.source_note(data)}"
    )
    return context, weather.fact_tokens(data)


def _distinctive_words(text, min_length=6):
    # A short label like "Exercise normal safety precautions" tends to get
    # paraphrased away, while longer words from the free text survive verbatim.
    return [word.strip(".,") for word in text.split() if len(word.strip(".,")) >= min_length]


def _live_rate_facts(currency_code):
    """Uses the same cached rates and wording as the guide page, so the
    assistant and the page never quote different figures."""
    try:
        data = exchange_rates.latest(currency_code)
    except (exchange_rates.LiveDataDisabled, exchange_rates.RatesUnavailable):
        return "Live exchange rates are not available right now, so do not quote any rate.", []

    lines = exchange_rates.rate_lines(data)
    context = (
        "Live exchange rates:\n"
        + "\n".join(f"- {line}" for line in lines)
        + f"\n{exchange_rates.source_note(data)}"
    )
    # The figure on the right of each line, such as 1.44 in "1 USD = 1.44 AUD".
    return context, [line.split(" = ")[1].split()[0] for line in lines]


def gather_guide_facts(intent, destination_id):
    """Returns (context_text, fact_tokens, has_data) for one guide category."""
    if intent == "currency":
        info = guide_collector.collect_currency(destination_id)
        if info is None:
            return "", [], False
        context = (
            f"Currency: {info['currency_code']}, the {info['currency_name']}. "
            f"{info['exchange_tips']}"
        )
        fact_tokens = [info["currency_code"]] + _distinctive_words(info["exchange_tips"])
        rate_context, rate_tokens = _live_rate_facts(info["currency_code"])
        return f"{context}\n{rate_context}", fact_tokens + rate_tokens, True

    if intent == "transport":
        items = guide_collector.collect_transportation(destination_id)
        if not items:
            return "", [], False
        context = "Transportation options:\n" + "\n".join(
            f"- {item['type']}: {item['description']} {item['tips']}" for item in items
        )
        return context, [item["type"] for item in items], True

    if intent == "visa":
        items = guide_collector.collect_visa(destination_id)
        if not items:
            return "", [], False
        context = "Visa requirements by nationality:\n" + "\n".join(
            f"- {item['nationality']}: {item['requirement_type']}. {item['notes']}"
            for item in items
        )
        fact_tokens = [item["requirement_type"] for item in items]
        for item in items:
            fact_tokens += _distinctive_words(item["notes"])
        return context, fact_tokens, True

    if intent == "weather":
        items = guide_collector.collect_weather(destination_id)
        if not items:
            return "", [], False
        destination = guide_collector.collect_destination(destination_id)
        active = _weather_active_month(items, destination and destination.get("timezone"))
        context = (
            f"It is currently {active['month']} there.\n"
            "Typical monthly weather (long-term averages, not a forecast):\n"
            + "\n".join(
                f"- {item['month']}: average daytime high {item['avg_temp']:g}C, {item['rainfall']:g}mm rainfall"
                for item in items
            )
            + f"\nBest time to visit: {active['best_visit_time']}"
        )
        # The context lists every month, and the question may name one that
        # isn't the current (default) month, so every month's figures are
        # valid facts, not just the active one.
        fact_tokens = [f"{item['avg_temp']:g}" for item in items] + [f"{item['rainfall']:g}" for item in items]
        # A best time to visit answer may quote no figure at all.
        fact_tokens += _distinctive_words(active["best_visit_time"])
        live_context, live_tokens = _live_weather_facts(destination)
        return f"{context}\n{live_context}", fact_tokens + live_tokens, True

    if intent == "safety":
        info = guide_collector.collect_safety(destination_id)
        if info is None:
            return "", [], False
        context = f"Safety level: {info['safety_level']}. {info['tips']}"
        fact_tokens = [info["safety_level"]] + _distinctive_words(info["tips"])
        return context, fact_tokens, True

    return "", [], False


def run_guide_chat(question, intent, destination):
    """Assembles the grounded context for `intent` and asks the model.
    Returns has_data False without calling the model when there is no data.
    """
    destination_label = f"{destination['city']}, {destination['country']}"
    context, fact_tokens, has_data = gather_guide_facts(intent, destination["id"])

    if not has_data:
        return {"answer": None, "has_data": False, "fact_tokens": []}

    system_prompt = load_prompt("implementation", "guide_chat_system.txt")
    full_context = f"Destination: {destination_label}\n{context}"

    answer = ask_ai(question=question, system=system_prompt, context=full_context)

    checks = {}
    if intent == "currency":
        checks = currency_checks(full_context)
    elif intent == "weather":
        checks = weather_checks(question, full_context)
    return {"answer": answer, "has_data": True, "fact_tokens": fact_tokens, "checks": checks}
