"""Act step: assemble grounded context for one guide category and ask the
model (student-4, Aurelia Sari).
"""

from datetime import datetime

from agentic_loop.collectors import guide_collector
from services import exchange_rates
from services.ai_client import ask_ai
from services.prompt_loader import load_prompt

GUIDE_SOURCE_PATH = "/student-4/#guides"


def _weather_active_month(items):
    current_month = datetime.now().strftime("%B")
    matching = [item for item in items if item["month"] == current_month]
    if matching:
        return matching[0]
    return items[0] if items else None


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
        active = _weather_active_month(items)
        context = (
            "Monthly weather:\n"
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
        return context, fact_tokens, True

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

    return {"answer": answer, "has_data": True, "fact_tokens": fact_tokens}
