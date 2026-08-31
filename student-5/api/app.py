"""Bookings & Budget API - Student 5 / Aung Ko Khaing.

Architecture:

Frontend -> Student-5 API -> Student-5 DB

AI:

Frontend -> Student-5 API -> AI-Mode -> Ollama -> LLM
"""

import os
from html import escape

import requests
from flask import Flask, Blueprint, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------
# FIX: the frontend calls everything under "/api/student-5/...",
# but every route below was previously registered on the bare
# app (e.g. "/flights/search" instead of
# "/api/student-5/flights/search"). That mismatch meant every
# fetch() from the browser hit a path Flask doesn't know about,
# so Flask returned its default HTML 404 page instead of JSON -
# which is exactly what produced:
#   "Unexpected token '<', "<!DOCTYPE "... is not valid JSON"
#
# Registering everything on a Blueprint with url_prefix
# "/api/student-5" makes the backend's routes match what the
# frontend actually requests.
# ---------------------------------------------------------
api = Blueprint("student5", __name__, url_prefix="/api/student-5")

DB_SERVICE_URL = os.getenv(
    "DB_SERVICE_URL",
    "http://student-5-db:5205",
)

AI_MODE_URL = os.getenv(
    "AI_MODE_URL",
    "http://ai-mode:5300",
)

DB_DOWN = "Could not reach the Bookings & Budget database service."


# =========================================================
# Utility functions
# =========================================================

def error_fragment(message, detail=""):
    body = f"<div class='notice notice-error'>{escape(message)}</div>"

    if detail:
        body += f"<pre>{escape(str(detail)[:600])}</pre>"

    return body


def db_get(path, params=None):
    response = requests.get(
        f"{DB_SERVICE_URL}{path}",
        params=params,
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def db_post(path, payload):
    response = requests.post(
        f"{DB_SERVICE_URL}{path}",
        json=payload,
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def db_put(path, payload):
    response = requests.put(
        f"{DB_SERVICE_URL}{path}",
        json=payload,
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def db_delete(path):
    response = requests.delete(
        f"{DB_SERVICE_URL}{path}",
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


# =========================================================
# Health
# =========================================================

# Kept at the bare root too (not just under the prefix) since
# container/orchestrator health checks (e.g. docker-compose
# healthcheck, k8s probes) conventionally hit "/health" directly
# rather than through the gateway prefix.
@app.get("/health")
@api.get("/health")
def health():
    return jsonify({
        "service": "student-5-api",
        "feature": "Bookings & Budget",
        "student": "Aung Ko Khaing",
        "status": "running",
    })


# =========================================================
# Budget
# =========================================================

@api.get("/budgets/<int:trip_id>")
def get_budget(trip_id):
    try:
        return jsonify(
            db_get(f"/budgets/{trip_id}")
        )
    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


@api.post("/budgets")
def create_budget():
    payload = request.get_json(silent=True) or {}

    required = [
        "trip_id",
        "total_budget",
    ]

    missing = [
        key for key in required
        if key not in payload
    ]

    if missing:
        return jsonify({
            "error": f"Missing fields: {', '.join(missing)}"
        }), 400

    try:
        return jsonify(
            db_post("/budgets", payload)
        ), 201

    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


@api.put("/budgets/<int:trip_id>")
def update_budget(trip_id):
    payload = request.get_json(silent=True) or {}

    try:
        return jsonify(
            db_put(f"/budgets/{trip_id}", payload)
        )

    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


# =========================================================
# Flight Search
# =========================================================

@api.get("/flights/search")
def search_flights():
    params = {
        key: value
        for key, value in request.args.items()
        if value.strip()
    }

    try:
        flights = db_get(
            "/flights/search",
            params=params,
        )

        ranked = rank_results(
            flights,
            price_key="price_aud",
        )

        return jsonify({
            "results": ranked,
            "count": len(ranked),
        })

    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


# =========================================================
# Hotel Search
# =========================================================

@api.get("/hotels/search")
def search_hotels():
    params = {
        key: value
        for key, value in request.args.items()
        if value.strip()
    }

    try:
        hotels = db_get(
            "/hotels/search",
            params=params,
        )

        ranked = rank_results(
            hotels,
            price_key="total_price_aud",
        )

        return jsonify({
            "results": ranked,
            "count": len(ranked),
        })

    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


# =========================================================
# Ranking algorithm
# =========================================================

def rank_results(results, price_key):
    """Weighted recommendation score.

    50% price
    30% rating
    20% popularity

    Lower price is better.
    Higher rating/popularity is better.
    """

    if not results:
        return []

    prices = [
        float(item.get(price_key, 0))
        for item in results
        if float(item.get(price_key, 0)) > 0
    ]

    max_price = max(prices) if prices else 1
    min_price = min(prices) if prices else 0

    price_range = max_price - min_price

    ranked = []

    for item in results:
        price = float(item.get(price_key, 0))

        if price_range:
            price_score = (
                (max_price - price) /
                price_range
            ) * 100
        else:
            price_score = 100

        rating_score = (
            float(item.get("rating", 0)) / 5
        ) * 100

        popularity_score = float(
            item.get("popularity_score", 0)
        )

        final_score = (
            price_score * 0.50
            + rating_score * 0.30
            + popularity_score * 0.20
        )

        item["recommendation_score"] = round(
            final_score,
            2,
        )

        ranked.append(item)

    ranked.sort(
        key=lambda item: item["recommendation_score"],
        reverse=True,
    )

    return ranked


# =========================================================
# Trip selections
# =========================================================

@api.get("/selections/<int:trip_id>")
def get_selections(trip_id):
    try:
        return jsonify(
            db_get(f"/selections/{trip_id}")
        )

    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


@api.post("/selections")
def add_selection():
    payload = request.get_json(silent=True) or {}

    required = [
        "trip_id",
        "item_type",
        "item_id",
        "item_name",
        "price_aud",
    ]

    missing = [
        key for key in required
        if key not in payload
    ]

    if missing:
        return jsonify({
            "error": f"Missing fields: {', '.join(missing)}"
        }), 400

    try:
        return jsonify(
            db_post("/selections", payload)
        ), 201

    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


@api.delete("/selections/<int:selection_id>")
def remove_selection(selection_id):
    try:
        return jsonify(
            db_delete(
                f"/selections/{selection_id}"
            )
        )

    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


# =========================================================
# Search history
# =========================================================

@api.get("/search-history/<int:trip_id>")
def get_search_history(trip_id):
    try:
        return jsonify(
            db_get(
                f"/search-history/{trip_id}"
            )
        )

    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


@api.post("/search-history")
def create_search_history():
    payload = request.get_json(silent=True) or {}

    try:
        return jsonify(
            db_post(
                "/search-history",
                payload,
            )
        ), 201

    except requests.RequestException as exc:
        return jsonify({
            "error": DB_DOWN,
            "detail": str(exc),
        }), 503


# =========================================================
# AI - Search Parsing
# =========================================================

@api.post("/ai/parse-search")
def ai_parse_search():
    question = request.form.get(
        "question",
        ""
    ).strip()

    if not question:
        return jsonify({
            "error": "Enter a search request."
        }), 400

    prompt = f"""
You are the NextStop travel search assistant.

Convert the user's natural-language travel request into
structured search information.

Return ONLY valid JSON with:

{{
    "search_type": "flight or hotel",
    "origin": "",
    "destination": "",
    "start_date": "",
    "end_date": "",
    "travellers": 1,
    "budget_aud": null
}}

User request:
{question}
"""

    try:
        response = requests.post(
            f"{AI_MODE_URL}/chat",
            json={
                "question": prompt,
                "context": (
                    "The assistant parses travel search requests "
                    "for the Bookings & Budget feature."
                ),
            },
            timeout=180,
        )

        response.raise_for_status()

        answer = response.json()["answer"]

        return jsonify({
            "question": question,
            "parsed_request": answer,
        })

    except requests.RequestException as exc:
        return jsonify({
            "error": "Could not reach AI-Mode.",
            "detail": str(exc),
        }), 503


# =========================================================
# AI - Recommendation explanation
# =========================================================

@api.post("/ai/explain-results")
def ai_explain_results():
    question = request.form.get(
        "question",
        "Which option is best?"
    )

    results = request.form.get(
        "results",
        ""
    )

    prompt = f"""
You are the NextStop travel recommendation assistant.

Explain which travel option is most suitable.

User request:
{question}

Available results:
{results}

Consider:
- price
- rating
- popularity
- value for money

Give a concise explanation.
"""

    try:
        response = requests.post(
            f"{AI_MODE_URL}/chat",
            json={
                "question": prompt,
                "context": results,
            },
            timeout=180,
        )

        response.raise_for_status()

        return jsonify({
            "answer": response.json()["answer"]
        })

    except requests.RequestException as exc:
        return jsonify({
            "error": "Could not reach AI-Mode.",
            "detail": str(exc),
        }), 503


# =========================================================
# AI - Budget advisor
# =========================================================

@api.post("/ai/budget-advisor")
def ai_budget_advisor():
    trip_id = request.form.get(
        "trip_id",
        ""
    )

    try:
        budget = db_get(
            f"/budgets/{trip_id}"
        )

        selections = db_get(
            f"/selections/{trip_id}"
        )

        context = f"""
Budget:
{budget}

Current selections:
{selections}
"""

        prompt = """
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

        response = requests.post(
            f"{AI_MODE_URL}/chat",
            json={
                "question": prompt,
                "context": context,
            },
            timeout=180,
        )

        response.raise_for_status()

        return jsonify({
            "answer": response.json()["answer"],
            "budget": budget,
            "selections": selections,
        })

    except requests.RequestException as exc:
        return jsonify({
            "error": "Could not complete budget analysis.",
            "detail": str(exc),
        }), 503


# =========================================================
# AI Chat
# =========================================================

@api.post("/ai/chat")
def ai_chat():
    question = request.form.get(
        "question",
        ""
    ).strip()

    trip_id = request.form.get(
        "trip_id",
        ""
    ).strip()

    if not question:
        return error_fragment(
            "Ask a question first."
        ), 400

    context_parts = []

    try:
        if trip_id:
            budget = db_get(
                f"/budgets/{trip_id}"
            )

            selections = db_get(
                f"/selections/{trip_id}"
            )

            context_parts.append(
                f"Budget: {budget}"
            )

            context_parts.append(
                f"Selections: {selections}"
            )

        flights = db_get(
            "/flights/search",
            {"destination": "Tokyo"},
        )

        hotels = db_get(
            "/hotels/search",
            {"destination": "Tokyo"},
        )

        context_parts.append(
            f"Example flights: {flights[:5]}"
        )

        context_parts.append(
            f"Example hotels: {hotels[:5]}"
        )

    except requests.RequestException as exc:
        return error_fragment(
            DB_DOWN,
            exc,
        ), 503

    context = "\n".join(context_parts)

    # -----------------------------------------------------
    # PLAN
    # -----------------------------------------------------
    plan = {
        "goal": "Answer travel and budget question",
        "actions": [
            "inspect trip budget",
            "inspect selected bookings",
            "use available travel results",
            "generate grounded response",
        ],
    }

    # -----------------------------------------------------
    # ACT
    # -----------------------------------------------------
    prompt = f"""
You are NextStop AI for the Bookings & Budget feature.

PLAN:
{plan}

Question:
{question}

Available database information:
{context}

Only use information available in the context.
If information is missing, say that it is unavailable.

Give a useful travel/budget response.
"""

    try:
        response = requests.post(
            f"{AI_MODE_URL}/chat",
            json={
                "question": prompt,
                "context": context,
            },
            timeout=180,
        )

        response.raise_for_status()

        answer = response.json()["answer"]

        # -------------------------------------------------
        # OBSERVE
        # -------------------------------------------------
        observation = {
            "database_context_available": bool(context),
            "answer_generated": bool(answer),
        }

        # -------------------------------------------------
        # ADAPT
        # -------------------------------------------------
        if not observation["answer_generated"]:
            answer = (
                "I could not generate a useful answer. "
                "Please try a more specific travel question."
            )

        return (
            "<div class='chat-msg user'>"
            "<div class='who'>You</div>"
            f"<div class='bubble'>{escape(question)}</div>"
            "</div>"

            "<div class='chat-msg bot'>"
            "<div class='who'>NextStop AI</div>"
            f"<div class='bubble'>{escape(answer)}</div>"
            "</div>"
        ), 200

    except requests.RequestException as exc:
        return error_fragment(
            "Could not reach the AI-Mode service.",
            exc,
        ), 503


app.register_blueprint(api)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5105,
    )