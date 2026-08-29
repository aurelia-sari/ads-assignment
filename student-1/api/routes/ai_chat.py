"""AI chatbot route - student-1's AI feature.

Grounds the model in the traveller's real trip data before answering, so the
chatbot talks about trips that exist rather than inventing them.
"""

import requests
from flask import Blueprint, request

from services import ai_mode, database_api, shared_api
from views.formatters import chat_exchange, error_fragment

ai_chat_bp = Blueprint("ai_chat", __name__)


def build_context(trip_id=None):
    """Summarise live trip data as plain text for the model."""
    try:
        if trip_id:
            trip_response = database_api.get_trip(trip_id)
            if trip_response.status_code != 200:
                return ""
            trip = trip_response.json()
            days = database_api.list_days(trip_id)
            traveller = shared_api.describe_traveller(
                trip["traveller_id"], shared_api.get_travellers()
            )
            lines = [
                f"Trip: {trip['trip_name']} to {trip['destination']}, "
                f"traveller {traveller}, "
                f"{trip['start_date']} to {trip['end_date']}, "
                f"budget AUD {trip['budget_aud']:.0f}, status {trip['status']}.",
                f"Itinerary has {len(days)} day(s):",
            ]
            lines += [
                f"  Day {day['day_number']} ({day['day_date']}) "
                f"{day['location']}: {day['activity']}"
                for day in days
            ]
            return "\n".join(lines)

        trips = database_api.list_trips()
        # This is a platform: these trips belong to different travellers. Saying
        # "the traveller has 12 trips" told the model twelve people's trips
        # belonged to one person, and it answered accordingly.
        owners = {trip["traveller_id"] for trip in trips}
        lines = [
            f"There are {len(trips)} trips in the system, "
            f"belonging to {len(owners)} different travellers:"
        ]
        # Budget was missing here, so any question about cost had nothing to
        # answer from and the model filled the gap by inventing figures.
        lines += [
            f"  #{trip['trip_id']} {trip['trip_name']} to {trip['destination']}, "
            f"{trip['start_date']} to {trip['end_date']}, "
            f"budget AUD {trip['budget_aud']:.0f}, {trip['status']}"
            for trip in trips
        ]
        return "\n".join(lines)
    except requests.RequestException:
        # The chatbot still answers without grounding rather than failing outright.
        return ""


@ai_chat_bp.post("/ai/chat")
def chat():
    question = request.form.get("question", "").strip()
    trip_id = request.form.get("trip_id", "").strip()

    if not question:
        return error_fragment("Ask a question first."), 400

    context = build_context(int(trip_id) if trip_id.isdigit() else None)

    try:
        answer = ai_mode.chat(question, context=context)
        return chat_exchange(question, answer), 200
    except requests.HTTPError as exc:
        detail = exc.response.json().get("hint", exc.response.text) if exc.response is not None else str(exc)
        return error_fragment("AI-Mode could not answer that.", detail), 503
    except requests.RequestException as exc:
        return error_fragment("Could not reach the AI-Mode service.", exc), 503
