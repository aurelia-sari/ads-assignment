"""Client for the shared AI-Mode service (student-4, Aurelia Sari).

Uses /recommend, not /chat, since it needs a per-turn system prompt and context.
"""

import os

import requests

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://ai-mode:5300")


def ask_ai(question, system, context="", max_tokens=300):
    response = requests.post(
        f"{AI_MODE_URL}/recommend",
        json={
            "question": question,
            "system": system,
            "context": context,
            "max_tokens": max_tokens,
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["answer"]
