"""Client for the shared AI-Mode service (student-4, Aurelia Sari).

Uses /recommend, not /chat, since it needs a per-turn system prompt and context.
AI-Mode does not run in CI, so AI_MODE_ENABLED=false switches it off there,
the same way MCP_ENABLED and RAG_ENABLED work.
"""

import os

import requests

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://host.docker.internal:5300")
AI_MODE_ENABLED = os.getenv("AI_MODE_ENABLED", "true").lower() not in ("false", "0", "no")


class AIModeDisabled(Exception):
    pass


def ask_ai(question, system, context="", max_tokens=300):
    if not AI_MODE_ENABLED:
        raise AIModeDisabled("AI-Mode is disabled in this environment (AI_MODE_ENABLED=false)")

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
