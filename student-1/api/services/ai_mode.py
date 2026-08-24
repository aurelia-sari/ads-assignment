"""Client for the shared AI-Mode service.

student-1-api never calls Ollama directly. The request flow is
Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM.
"""

import os

import requests

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://ai-mode:5300")


def chat(question, context="", max_tokens=300):
    response = requests.post(
        f"{AI_MODE_URL}/chat",
        json={"question": question, "context": context, "max_tokens": max_tokens},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["answer"]
