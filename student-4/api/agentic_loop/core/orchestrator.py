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

UNRELATED_MESSAGE = (
    "I can only help with a destination's currency, transportation, visa, "
    "weather and safety guide. Ask me about one of those, naming a city."
)

NO_CITY_MESSAGE = "Which city would you like to know about? Try naming one, like Sydney or Cairns."


def run(question, resolve_destination):
    """resolve_destination is only called for a guide-category question,
    since other intents (another feature, unrelated) need no destination.
    """
    redirect_map = guide_collector.collect_redirect_map()
    intent, redirect_row = classify_intent(question, redirect_map)

    if intent == "unrelated":
        return {"intent": intent, "answer": UNRELATED_MESSAGE, "adapted": False}

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
        return {"intent": intent, "answer": NO_CITY_MESSAGE, "adapted": True}

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
