"""Observe step: confirm the model's answer restates a real retrieved fact
instead of inventing one (student-4, Aurelia Sari).
"""


def validate_answer(answer, fact_tokens):
    if not answer or not answer.strip():
        return {"valid": False, "reason": "low_confidence"}

    if fact_tokens and not any(str(token) in answer for token in fact_tokens):
        return {"valid": False, "reason": "low_confidence"}

    return {"valid": True, "reason": None}
