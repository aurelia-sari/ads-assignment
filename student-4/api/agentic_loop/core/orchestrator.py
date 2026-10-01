"""Plan -> Act -> Observe -> Adapt orchestration for the Travel Guides AI
assistant (student-4, Aurelia Sari).

Plan: classify the question. Act: retrieve that category's data and ask
the model. Observe: check the answer restates a real fact, retrying once.
Adapt: missing data, another feature, or low confidence each get their
own fallback response instead of a guess.
"""

from agentic_loop.collectors import guide_collector
from agentic_loop.core import currency_request
from agentic_loop.core.classifier import classify_intent
from agentic_loop.core.validator import validate_answer
from agentic_loop.pipelines.guide_chat_pipeline import GUIDE_SOURCE_PATH, run_guide_chat
from services import exchange_rates

GUIDE_TOPICS = "currency, transportation, visa, weather and safety"


def _join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _coverage():
    """Names every seeded city by country, read from the database so it
    always matches the guides that exist."""
    by_country = {}
    destinations = guide_collector.collect_destinations()
    for destination in sorted(destinations, key=lambda d: (d["country"], d["city"])):
        by_country.setdefault(destination["country"], []).append(destination["city"])
    return _join([f"{country} ({_join(cities)})" for country, cities in by_country.items()]) if by_country else ""


def unrelated_message():
    coverage = _coverage()
    where = f" for {coverage}" if coverage else ""
    return f"I can only help with the {GUIDE_TOPICS} guide{where}. Ask me about one of those, naming a city."


SUPPORTED_CURRENCY_TEXT = _join(exchange_rates.SUPPORTED_CURRENCIES)


def _shown_amount(amount, code):
    return f"{amount:,.0f}" if amount == int(amount) else exchange_rates.format_amount(amount, code)


def answer_currency_request(request, resolve_destination):
    """Act and Adapt for a question that names a currency. Returns None when
    it is not a conversion, so the normal guide answer runs instead."""
    def reply(answer):
        return {"intent": "currency", "answer": answer, "adapted": True}

    if request["kind"] == "unsupported":
        return reply(
            f"Only {SUPPORTED_CURRENCY_TEXT} are available at the moment, so I cannot "
            f"convert {_join(request['names'])}."
        )
    if request["kind"] == "ambiguous_dollar":
        return reply("Which dollar do you mean? I can convert US dollars (USD) and Australian dollars (AUD).")

    codes = request["currencies"]
    if request["amount"] is None and not request["asks_rate"]:
        return None

    # Also starts a chat session when the question names a city.
    destination = resolve_destination()
    if len(codes) == 1 and destination is not None:
        currency = guide_collector.collect_currency(destination["id"])
        if currency and currency["currency_code"] != codes[0]:
            codes = codes + [currency["currency_code"]]
    if len(codes) < 2:
        # Only the city's own currency, as in "is 50000 yen enough in Tokyo",
        # which the guide answers better than a conversion.
        if destination is not None:
            return None
        others = _join([code for code in exchange_rates.SUPPORTED_CURRENCIES if code != codes[0]])
        return reply(f"Which currency should I convert {codes[0]} to? I can use {others}.")

    from_code, to_code = codes[0], codes[1]
    amount = request["amount"] if request["amount"] is not None else 1
    try:
        converted, rate, data = exchange_rates.convert(amount, from_code, to_code)
    except (exchange_rates.LiveDataDisabled, exchange_rates.RatesUnavailable):
        return reply(
            "Live exchange rates are not available right now, so I cannot convert amounts. "
            f"The currency tips are on the guide page here: {GUIDE_SOURCE_PATH}"
        ) | {"redirect_path": GUIDE_SOURCE_PATH}

    # Quoted and rounded the same way as the rate tiles on the page.
    unit = 100 if from_code in exchange_rates.PER_HUNDRED else 1
    shown_rate = exchange_rates.format_amount(rate * unit, to_code)
    return {
        "intent": "currency",
        "answer": (
            f"{_shown_amount(amount, from_code)} {from_code} is about "
            f"{exchange_rates.format_amount(converted, to_code)} {to_code}, at {unit} {from_code} = "
            f"{shown_rate} {to_code}. {exchange_rates.source_note(data)}"
        ),
        "adapted": False,
    }


# Also covers a city or country without a guide, since an unknown place
# name cannot be told apart from no place name at all.
def no_city_message():
    coverage = _coverage()
    if not coverage:
        return "Which city would you like to know about?"
    return f"I only have guides for {coverage}. Which of these cities would you like to know about?"


def run(question, resolve_destination):
    """resolve_destination is not called for another feature's question,
    since a redirect needs no destination.
    """
    redirect_map = guide_collector.collect_redirect_map()
    intent, redirect_row = classify_intent(question, redirect_map)

    if intent in ("currency", "unrelated"):
        request = currency_request.parse(question)
        if request is not None:
            result = answer_currency_request(request, resolve_destination)
            if result is not None:
                return result

    if intent == "unrelated":
        # A bare city name, often a reply to the no city prompt, starts a
        # session for that city so the follow up topic question uses it.
        destination = resolve_destination()
        if destination is not None and destination["city"].lower() in question.lower():
            return {
                "intent": intent,
                "answer": (
                    f"What would you like to know about {destination['city']}, "
                    f"{destination['country']}? I can help with its {GUIDE_TOPICS}."
                ),
                "adapted": True,
            }
        return {"intent": intent, "answer": unrelated_message(), "adapted": False}

    if intent.startswith("other:"):
        feature_name = redirect_row["feature_name"]
        path = redirect_row["redirect_path_template"]
        return {
            "intent": intent,
            "answer": f"That sounds like a job for {feature_name}. Open it here: {path}",
            "adapted": True,
            "redirect_path": path,
        }

    destination = resolve_destination()
    if destination is None:
        return {"intent": intent, "answer": no_city_message(), "adapted": True}

    destination_label = f"{destination['city']}, {destination['country']}"
    result = run_guide_chat(question, intent, destination)

    if not result["has_data"]:
        return {
            "intent": intent,
            "answer": (
                f"I don't have {intent} information for {destination_label} yet. "
                f"See what is on the guide page here: {GUIDE_SOURCE_PATH}"
            ),
            "adapted": True,
            "redirect_path": GUIDE_SOURCE_PATH,
        }

    validation = validate_answer(result["answer"], result["fact_tokens"], **result.get("checks", {}))
    if validation["valid"]:
        return {"intent": intent, "answer": result["answer"], "adapted": False}

    retry_question = (
        f"{question}\n\n"
        "Important: answer using only the exact facts given above. If you "
        "are not sure, say which detail you need clarified."
    )
    retry_result = run_guide_chat(retry_question, intent, destination)
    retry_validation = validate_answer(
        retry_result["answer"], retry_result["fact_tokens"], **retry_result.get("checks", {})
    )

    if retry_validation["valid"]:
        return {"intent": intent, "answer": retry_result["answer"], "adapted": False}

    # The guide's own payment advice is short and always correct, so it is
    # quoted instead of asking the traveller to rephrase.
    currency = guide_collector.collect_currency(destination["id"]) if intent == "currency" else None
    if currency:
        return {
            "intent": intent,
            "answer": f"Here is what the guide says for {destination_label}. {currency['exchange_tips']}",
            "adapted": True,
            "redirect_path": GUIDE_SOURCE_PATH,
        }

    return {
        "intent": intent,
        "answer": (
            f"I want to get this right for {destination_label}. Could you say "
            f"more specifically what about {intent} you would like to know?"
        ),
        "adapted": True,
    }
