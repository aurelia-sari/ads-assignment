"""Client for the shared AI-Mode service.

student-1-api never calls Ollama directly. The request flow is
Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM.

AI-Mode is not containerised, so in Docker it is reached through
host.docker.internal. In CI it is not running at all, which is what
AI_MODE_ENABLED=false is for, the same way MCP_ENABLED and RAG_ENABLED work.
"""

import os

import requests

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://host.docker.internal:5300")
AI_MODE_ENABLED = os.getenv("AI_MODE_ENABLED", "true").lower() not in ("false", "0", "no")


class AIModeDisabled(Exception):
    """Raised when AI-Mode is switched off for this environment, as it is in CI."""


def chat(question, context="", max_tokens=300):
    if not AI_MODE_ENABLED:
        raise AIModeDisabled("AI-Mode is disabled in this environment (AI_MODE_ENABLED=false)")

    response = requests.post(
        f"{AI_MODE_URL}/chat",
        json={"question": question, "context": context, "max_tokens": max_tokens},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["answer"]
