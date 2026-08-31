from flask import Blueprint, jsonify, request
from views.ai_formatter import format_recommendation
from agentic_loop.core.orchestrator import run_agentic_recommendation
from services.database_api import create_recommendation

import json


ai_mode_bp = Blueprint("ai_mode", __name__)


@ai_mode_bp.post("/ai/recommend")
def recommend():
    payload = request.get_json(silent=True) or {}

    question = (
        payload.get("question")
        or request.form.get("question")
        or ""
    ).strip()

    user_id = payload.get("user_id")

    if not question:
        return jsonify({
            "error": "question is required"
        }), 400

    if user_id is not None and not isinstance(user_id, int):
        return jsonify({
            "error": "user_id must be an integer"
        }), 400

    try:
        result = run_agentic_recommendation(question)

        # Save valid recommendation result to DB
        if result["validation"]["valid"]:

            recommendation_data = {
                "answer": result["answer"],
                "place_ids": [
                    place["id"]
                    for place in result["places"]
                ],
            }

            recommendation_payload = {
                "user_id": user_id,
                "question": question,
                "preferences": None,
                "location": "Sydney",
                "recommendation_result": json.dumps(
                    recommendation_data,
                    ensure_ascii=False,
                ),
            }

            create_recommendation(
                recommendation_payload
            )

        # Return result to HTML
        if request.headers.get("HX-Request"):
            return format_recommendation(
                question,
                result
            )

        return jsonify(result)

    except Exception as exc:
        return jsonify({
            "error": "Recommendation failed",
            "detail": str(exc)
        }), 500