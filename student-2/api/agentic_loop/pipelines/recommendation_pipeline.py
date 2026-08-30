import json

from agentic_loop.collectors.place_collector import collect_places
from agentic_loop.core.validator import validate_recommendation
from services.ai_client import ask_ai
from services.prompt_loader import load_prompt


MAX_RECOMMENDATIONS = 3


def run_recommendation(question):
    places = collect_places()
    question_lower = question.lower()

    candidates = places

    # =========================================================
    # Category filtering
    # =========================================================

    if "restaurant" in question_lower:
        candidates = [
            place for place in candidates
            if place.get("category") == "restaurant"
        ]

    if "attraction" in question_lower:
        candidates = [
            place for place in candidates
            if place.get("category") == "attraction"
        ]

    if "activities" in question_lower or "activity" in question_lower:
        candidates = [
            place for place in candidates
            if place.get("category") == "activities"
        ]

    # =========================================================
    # Cheapest
    # =========================================================

    if "cheap" in question_lower and candidates:
        priced_candidates = [
            place for place in candidates
            if place.get("price_range") is not None
        ]

        if priced_candidates:
            min_price = min(
                place["price_range"]
                for place in priced_candidates
            )

            candidates = [
                place for place in priced_candidates
                if place["price_range"] == min_price
            ]

    # =========================================================
    # Most expensive
    # =========================================================

    if "expensive" in question_lower and candidates:
        priced_candidates = [
            place for place in candidates
            if place.get("price_range") is not None
        ]

        if priced_candidates:
            max_price = max(
                place["price_range"]
                for place in priced_candidates
            )

            candidates = [
                place for place in priced_candidates
                if place["price_range"] == max_price
            ]

    # =========================================================
    # Highest rated
    # =========================================================

    if (
        "highest rated" in question_lower
        or "best rated" in question_lower
    ) and candidates:

        rated_candidates = [
            place for place in candidates
            if place.get("rating") is not None
        ]

        if rated_candidates:
            max_rating = max(
                place["rating"]
                for place in rated_candidates
            )

            candidates = [
                place for place in rated_candidates
                if place["rating"] == max_rating
            ]

    # =========================================================
    # Decide whether user wants one or multiple recommendations
    # =========================================================

    single_result_terms = [
        "one ",
        "one restaurant",
        "one place",
        "one attraction",
        "most expensive",
        "highest rated",
        "best rated",
        "best place",
        "best restaurant",
    ]

    wants_single_result = any(
        term in question_lower
        for term in single_result_terms
    )

    max_results = (
        1
        if wants_single_result
        else MAX_RECOMMENDATIONS
    )

    # Do not send too many records to the small local model
    candidates_for_ai = candidates[:max_results]

    # =========================================================
    # AI prompt
    # =========================================================

    system_prompt = load_prompt(
        "implementation",
        "recommendation_system.txt"
    )

    context = json.dumps(
        candidates_for_ai,
        ensure_ascii=False,
        indent=2
    )

    answer = ask_ai(
        question=question,
        system=system_prompt,
        context=context,
    )

    # =========================================================
    # Validate AI answer
    # =========================================================

    validation = validate_recommendation(
        answer,
        candidates_for_ai
    )

    selected_places = []

    if validation["valid"]:
        selected_places = [
            place
            for place in candidates_for_ai
            if place["name"] in validation["place_names"]
        ]

    return {
        "answer": answer,
        "validation": validation,
        "places": selected_places,
    }