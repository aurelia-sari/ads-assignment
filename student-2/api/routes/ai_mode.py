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

    if not question:
        return jsonify({
            "error": "question is required"
        }), 400

    try:
        result = run_agentic_recommendation(question)
        
        # Save result to db
        if result["validation"]["valid"]:

            recommendation_data = {
                "answer": result["answer"],
                "place_ids": [
                    place["id"]
                    for place in result["places"]
                ],
            }

            recommendation_payload = {
                "user_id": "guest",
                "question": question,
                "preferences": None,
                "location": "Sydney",
                "recommendation_result": json.dumps(
                    recommendation_data,
                    ensure_ascii=False,
                ),
            }
        
        create_recommendation(recommendation_payload)
        
        # Return result to html
        if request.headers.get("HX-Request"):
            return format_recommendation(question, result)

        return jsonify(result)

    except Exception as exc:
        return jsonify({
            "error": "Recommendation failed",
            "detail": str(exc)
        }), 500