"""Plan -> Act -> Observe -> Adapt orchestration for the Travel Guides AI
assistant (student-4, Aurelia Sari).

Plan: classify the question. Act: retrieve that category's data and ask
the model. Observe: check the answer restates a real fact, retrying once.
Adapt: missing data, another feature, or low confidence each get their
own fallback response instead of a guess.
"""

from agentic_loop.collectors import guide_collector
from agentic_loop.core.classifier import classify_intent
from agentic_loop.core.validator import validate_answer
from agentic_loop.pipelines.guide_chat_pipeline import GUIDE_SOURCE_PATH, run_guide_chat

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

    validation = validate_answer(result["answer"], result["fact_tokens"])
    if validation["valid"]:
        return {"intent": intent, "answer": result["answer"], "adapted": False}

    retry_question = (
        f"{question}\n\n"
        "Important: answer using only the exact facts given above. If you "
        "are not sure, say which detail you need clarified."
    )
    retry_result = run_guide_chat(retry_question, intent, destination)
    retry_validation = validate_answer(retry_result["answer"], retry_result["fact_tokens"])

    if retry_validation["valid"]:
        return {"intent": intent, "answer": retry_result["answer"], "adapted": False}

    return {
        "intent": intent,
        "answer": (
            f"I want to get this right for {destination_label}. Could you say "
            f"more specifically what about {intent} you would like to know?"
        ),
        "adapted": True,
    }
