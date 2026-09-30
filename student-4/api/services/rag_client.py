"""Client for the shared RAG server (student-4, Aurelia Sari).

Grounding, citations and the confidence category are all computed by the
shared server. This client only forwards the question.
"""

import os

import requests

RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://host.docker.internal:5500")
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() not in ("false", "0", "no")

# Generation runs on a local model through AI-Mode, so a cold start can be slow.
TIMEOUT = 180


class RAGDisabled(Exception):
    pass


def ask(question):
    if not RAG_ENABLED:
        raise RAGDisabled("RAG is disabled in this environment (RAG_ENABLED=false)")

    response = requests.post(f"{RAG_SERVER_URL}/ask", json={"question": question}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def health():
    if not RAG_ENABLED:
        raise RAGDisabled("RAG is disabled in this environment (RAG_ENABLED=false)")
    response = requests.get(f"{RAG_SERVER_URL}/health", timeout=3)
    response.raise_for_status()
    return response.json()
