"""Observe step: confirm the model's answer restates a real retrieved fact
instead of inventing one (student-4, Aurelia Sari).
"""

import re

FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalise_figure(text):
    # "1,250.50" and "0.910" are read as the same figures as "1250.5" and "0.91".
    value = text.replace(",", "")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value.lstrip("0") or "0"


def figures_in(text):
    return {normalise_figure(match) for match in FIGURE.findall(text)}


def validate_answer(answer, fact_tokens, forbidden=(), known_figures=None):
    """forbidden holds patterns for claims the guide contradicts. When
    known_figures is given, every number in the answer must be one of them."""
    if not answer or not answer.strip():
        return {"valid": False, "reason": "low_confidence"}

    if fact_tokens and not any(str(token) in answer for token in fact_tokens):
        return {"valid": False, "reason": "low_confidence"}

    if any(pattern.search(answer) for pattern in forbidden):
        return {"valid": False, "reason": "contradicts_guide"}

    if known_figures is not None and not figures_in(answer) <= known_figures:
        return {"valid": False, "reason": "unknown_figure"}

    return {"valid": True, "reason": None}
