import os
import requests


AI_MODE_URL = os.getenv(
    "AI_MODE_URL",
    "http://ai-mode:5300"
)


def ask_ai(question, system=None, context=None, max_tokens=300):
    payload = {
        "question": question,
        "max_tokens": max_tokens,
    }

    if system:
        payload["system"] = system

    if context:
        payload["context"] = context

    response = requests.post(
        f"{AI_MODE_URL}/recommend",
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return data["answer"]