"""AI budget advisor route - student-5's AI feature.

Reviews a trip's real budget against what was actually spent on its
selections before answering, so the advice is grounded in numbers that exist
rather than invented ones. Returns JSON (not an HTML fragment) since the
frontend reads answer/budget/selections as separate fields rather than
swapping in rendered markup.
"""

import requests
from flask import Blueprint, jsonify, request

from services import aiMode, dbApi

ai_budget_bp = Blueprint("ai_budget", __name__)

DB_DOWN = "Could not complete budget analysis."

ADVISOR_PROMPT = """
You are the NextStop budget advisor.

Review the travel budget and current selections.

Determine:
1. Whether the traveller is within budget.
2. How much has been spent.
3. How much remains.
4. Whether flight/hotel spending is balanced.
5. One practical recommendation.

Do not invent prices.
"""


def spend_by_type(selections):
    totals = {"flight": 0.0, "hotel": 0.0}
    for row in selections:
        totals[row["item_type"]] = totals.get(row["item_type"], 0.0) + row["price_aud"]
    return totals


def build_context(budget, selections):
    lines = []

    if budget:
        lines.append(
            f"Budget: total AUD {budget['total_budget']:.0f}, "
            f"flight allocation AUD {budget['flight_budget']:.0f}, "
            f"hotel allocation AUD {budget['hotel_budget']:.0f}."
        )
    else:
        lines.append("No budget has been set for this trip yet.")

    spent = spend_by_type(selections)
    lines.append(
        f"Actually spent so far: flights AUD {spent['flight']:.0f}, "
        f"hotels AUD {spent['hotel']:.0f}, "
        f"total AUD {sum(spent.values()):.0f}."
    )
    lines.append(f"{len(selections)} item(s) selected in total.")

    return "\n".join(lines)


@ai_budget_bp.post("/ai/budget-advisor")
def budget_advisor():
    trip_id = request.form.get("trip_id", "").strip()

    if not trip_id:
        return jsonify({"error": "Select a trip first."}), 400

    try:
        budget_response = dbApi.get_budget(trip_id)
        budget = budget_response.json() if budget_response.status_code == 200 else None
        selections = dbApi.list_selections(trip_id)
    except requests.RequestException as exc:
        return jsonify({"error": DB_DOWN, "detail": str(exc)}), 503

    context = build_context(budget, selections)

    try:
        answer = aiMode.chat(ADVISOR_PROMPT, context=context)
    except requests.HTTPError as exc:
        detail = exc.response.json().get("hint", exc.response.text) if exc.response is not None else str(exc)
        return jsonify({"error": "AI-Mode could not answer that.", "detail": detail}), 503
    except requests.RequestException as exc:
        return jsonify({"error": "Could not reach the AI-Mode service.", "detail": str(exc)}), 503

    return jsonify({"answer": answer, "budget": budget, "selections": selections})