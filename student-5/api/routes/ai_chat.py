"""Student 5 - Aung Ko Khaing
AI assistant chat for Bookings & Budget.
"""

from flask import Blueprint, request

from services import ai_mode, database_api, mcp_client, rag_client
from views.formatters import chat_exchange, error_fragment

ai_chat_bp = Blueprint("ai_chat", __name__)


def build_context(trip_id=None):

    lines = []
    mcp_notes = []

    if trip_id:
        budget_response = database_api.get_budget(trip_id)
        if budget_response.ok:
            budget = budget_response.json()
            lines.append(
                f"Budget for trip {trip_id}: total ${budget['total_budget']:,.0f} "
                f"AUD (flights ${budget['flight_budget']:,.0f}, "
                f"hotels ${budget['hotel_budget']:,.0f})."
            )

        selections = database_api.list_selections(trip_id)
        if selections:
            items = "; ".join(
                f"{s['item_type']}: {s['item_name']} (${s['price_aud']:,.0f})"
                for s in selections
            )
            lines.append(f"Selected for trip {trip_id}: {items}.")

    flights = database_api.search_flights({"destination": "Melbourne"})
    if flights:
        sample = flights[0]
        lines.append(
            f"Example flight: {sample['airline']} {sample['flight_number']} "
            f"{sample['origin']} -> {sample['destination']} on "
            f"{sample['departure_date']}, ${sample['price_aud']:,.0f} AUD."
        )

    hotels = database_api.search_hotels({"destination": "Melbourne"})
    if hotels:
        sample = hotels[0]
        lines.append(
            f"Example hotel: {sample['name']} in {sample['destination']}, "
            f"${sample['price_per_night_aud']:,.0f} AUD/night."
        )

    destination = flights[0]["destination"] if flights else "Melbourne"
    mcp_flight_rows = mcp_client.search_flights(destination=destination)
    if mcp_flight_rows:
        mcp_notes.append(
            f"search_flights(destination=\"{destination}\") -> "
            f"{len(mcp_flight_rows)} row(s) (student-5's own data, read via MCP)"
        )
    guide_rows = mcp_client.lookup_destination_guide(destination)
    if guide_rows:
        guide = guide_rows[0]
        summary = guide.get("summary") or guide.get("description") or ""
        if summary:
            lines.append(f"Destination guide ({destination}, via MCP/student-4): {summary}")
            mcp_notes.append(
                f"lookup_destination_guide(query=\"{destination}\") -> "
                f"1 of {len(guide_rows)} row(s) used"
            )

    place_rows = mcp_client.search_places(name=destination)
    if place_rows:
        names = ", ".join(p.get("name", "") for p in place_rows[:3] if p.get("name"))
        if names:
            lines.append(f"Things to do in {destination} (via MCP/student-2): {names}.")
            mcp_notes.append(
                f"search_places(name=\"{destination}\") -> {len(place_rows)} row(s), "
                f"e.g. {names}"
            )

    return "\n".join(lines), mcp_notes


@ai_chat_bp.post("/ai/chat")
def chat():
    question = (request.form.get("question") or "").strip()
    trip_id = (request.form.get("trip_id") or "").strip() or None

    if not question:
        return error_fragment("Please enter a question."), 400

    context, mcp_notes = build_context(trip_id)

    try:
        result = rag_client.ask(question, context=context)
        answer = result.get("answer", "")
        citations = result.get("citations") or []
        confidence = result.get("confidence")
        confidence_reason = result.get("confidence_reason")
        return chat_exchange(
            question,
            answer,
            citations=citations,
            confidence=confidence,
            confidence_reason=confidence_reason,
            mcp_notes=mcp_notes,
        )
    except rag_client.RagError:
        try:
            result = ai_mode.chat(question, context=context)
            return chat_exchange(
                question, result.get("answer", ""), mcp_notes=mcp_notes
            )
        except Exception as exc:
            return error_fragment(
                "AI-Mode could not answer that.",
                "Check Ollama is running and the model is pulled, and that "
                "the RAG/MCP servers are running on the host if you expect "
                f"cited answers. Detail: {exc}",
            )