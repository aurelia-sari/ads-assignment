"""Client for the shared RAG server.

Every feature asks the same shared RAG server, so grounding, citations and the
confidence category are computed in one place rather than five.

student-1-api may pass live trip data alongside the question. The RAG server
labels that separately from the retrieved passages, so a live row can resolve
what the traveller is referring to without being presented as a cited source.
"""

import os

import requests

RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://host.docker.internal:5500")
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() not in ("false", "0", "no")

TIMEOUT = 180


class RAGDisabled(Exception):
    """Raised when RAG is switched off for this environment, as it is in CI."""


def ask(question, context="", top_k=4):
    """Ask a grounded question.

    The response always carries a confidence category and, unless it is an
    insufficient-context refusal, a list of citations.
    """
    if not RAG_ENABLED:
        raise RAGDisabled("RAG is disabled in this environment (RAG_ENABLED=false)")

    response = requests.post(
        f"{RAG_SERVER_URL}/ask",
        json={"question": question, "context": context, "top_k": top_k},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()
