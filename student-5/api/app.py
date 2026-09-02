"""Bookings & Budget API - Student 5 / Aung Ko Khaing.

Architecture:

Frontend -> Student-5 API -> Student-5 DB

AI:

Frontend -> Student-5 API -> AI-Mode -> Ollama -> LLM
"""

import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from route.ai_chat import ai_chat_bp
from route.ai_budget import ai_budget_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(ai_chat_bp)
app.register_blueprint(ai_budget_bp)

# the frontend nginx container proxies and strips that prefix already.

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

@app.get("/health")
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

@app.get("/budgets/<int:trip_id>")
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


@app.post("/budgets")
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


@app.put("/budgets/<int:trip_id>")
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

@app.get("/flights/search")
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

@app.get("/hotels/search")
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

@app.get("/selections/<int:trip_id>")
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


@app.post("/selections")
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


@app.delete("/selections/<int:selection_id>")
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

@app.get("/search-history/<int:trip_id>")
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


@app.post("/search-history")
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

@app.post("/ai/parse-search")
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

@app.post("/ai/explain-results")
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


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5105,
    )