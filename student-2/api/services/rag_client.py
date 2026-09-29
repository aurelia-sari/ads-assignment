"""RAG client for Student 2."""

import os

import requests


RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://host.docker.internal:5500")
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() not in ("false", "0", "no")
TIMEOUT = float(os.getenv("RAG_TIMEOUT", "190"))


class RAGDisabled(Exception):
    pass


class RAGUpstreamError(Exception):
    def __init__(self, payload, status_code):
        super().__init__(payload.get("error", "Shared RAG request failed."))
        self.payload = payload
        self.status_code = status_code


class RAGProtocolError(Exception):
    pass


# Send a request to shared RAG
def _post(path, payload=None):
    if not RAG_ENABLED:
        raise RAGDisabled("RAG is disabled in this environment.")

    response = requests.post(
        f"{RAG_SERVER_URL}{path}",
        json=payload or {},
        timeout=TIMEOUT,
    )
    try:
        body = response.json()
    except ValueError as exc:
        raise RAGProtocolError("Shared RAG returned a non-JSON response.") from exc

    if not response.ok:
        if not isinstance(body, dict):
            body = {"error": "Shared RAG request failed."}
        raise RAGUpstreamError(body, response.status_code)
    if not isinstance(body, dict):
        raise RAGProtocolError("Shared RAG returned an invalid response.")
    return body


# Refresh knowledge
def reindex():
    return _post("/reindex")


# Retrieve context
def search(question):
    return _post("/search", {"question": question})


# Ask a grounded question
def ask(question):
    return _post("/ask", {"question": question})
