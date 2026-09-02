"""AI chatbot route - student-5's AI feature.

Grounds the model in the trip's real budget and selections, plus a few live
search examples, before answering - so the chatbot talks about numbers that
exist rather than inventing them.
"""

import requests
from flask import Blueprint, request

from services import aiMode, dbApi
from views.formatters import chat_exchange, error_fragment

ai_chat_bp = Blueprint("ai_chat", __name__)


def build_context(trip_id=None):
    """Summarise live budget/selection/search data as plain text for the model."""
    lines = []

    try:
        if trip_id:
            budget_response = dbApi.get_budget(trip_id)
            if budget_response.status_code == 200:
                budget = budget_response.json()
                lines.append(
                    f"Budget for trip {trip_id}: total AUD {budget['total_budget']:.0f}, "
                    f"flight allocation AUD {budget['flight_budget']:.0f}, "
                    f"hotel allocation AUD {budget['hotel_budget']:.0f}."
                )
            else:
                lines.append(f"No budget has been set for trip {trip_id} yet.")

            selections = dbApi.list_selections(trip_id)
            if selections:
                spent = sum(row["price_aud"] for row in selections)
                lines.append(
                    f"Trip {trip_id} has {len(selections)} selection(s), "
                    f"totalling AUD {spent:.0f}:"
                )
                lines += [
                    f"  {row['item_type']}: {row['item_name']} - AUD {row['price_aud']:.0f}"
                    for row in selections
                ]
            else:
                lines.append(f"Trip {trip_id} has no selections yet.")

        # A few live examples so the model has something concrete to reason
        # about even when there is no trip in context yet.
        flights = dbApi.search_flights({"destination": "Tokyo"})
        if flights:
            lines.append("Example flights currently available:")
            lines += [
                f"  {flight['airline']} {flight['flight_number']} "
                f"{flight['origin']} -> {flight['destination']}, "
                f"AUD {flight['price_aud']:.0f}, rating {flight['rating']}/5"
                for flight in flights[:5]
            ]

        hotels = dbApi.search_hotels({"destination": "Tokyo"})
        if hotels:
            lines.append("Example hotels currently available:")
            lines += [
                f"  {hotel['name']} ({hotel['destination']}), "
                f"AUD {hotel['total_price_aud']:.0f} total, rating {hotel['rating']}/5"
                for hotel in hotels[:5]
            ]
    except requests.RequestException:
        # The chatbot still answers without grounding rather than failing outright.
        pass

    return "\n".join(lines)


@ai_chat_bp.post("/ai/chat")
def chat():
    question = request.form.get("question", "").strip()
    trip_id = request.form.get("trip_id", "").strip()

    if not question:
        return error_fragment("Ask a question first."), 400

    context = build_context(int(trip_id) if trip_id.isdigit() else None)

    try:
        answer = aiMode.chat(question, context=context)
        return chat_exchange(question, answer), 200
    except requests.HTTPError as exc:
        detail = exc.response.json().get("hint", exc.response.text) if exc.response is not None else str(exc)
        return error_fragment("AI-Mode could not answer that.", detail), 503
    except requests.RequestException as exc:
        return error_fragment("Could not reach the AI-Mode service.", exc), 503