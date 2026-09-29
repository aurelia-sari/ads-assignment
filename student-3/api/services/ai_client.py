"""Client for the shared AI-Mode service (student-3, Tanishpreet Kour).

Uses /recommend, since it needs a per-call system prompt.
"""

import os

import requests

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://ai-mode:5300")
    
    
def ask_ai(question, system, max_tokens=500):
    response = requests.post(
        f"{AI_MODE_URL}/recommend",
        json={"question": question, "system": system, "max_tokens": max_tokens},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["answer"]