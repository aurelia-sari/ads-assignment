"""Student 5 - Aung Ko Khaing
Client for the shared RAG server (Release 1).

"""

import os

import requests

RAG_URL = os.getenv("RAG_URL", "http://host.docker.internal:5500")
ASK_TIMEOUT = 185   # retrieval + generation; generation alone can take ~180s
SEARCH_TIMEOUT = 15  # retrieval only, no model call


class RagError(Exception):
    """Raised when the RAG server cannot be reached or returns an error."""


def ask(question, context="", top_k=4, max_tokens=350):
    """Retrieve relevant knowledge-base passages and generate a cited answer.

    `context` is student-5's own live application data (budget, selections,
    search results) plus anything pulled cross-feature through mcp_client -
    the RAG server keeps this clearly separate from the cited knowledge-base
    text so the model can't pass off live numbers as a cited source.

    Returns the full RAG response dict: answer, confidence,
    confidence_reason, citations, grounded, model. When nothing in the
    knowledge base is relevant, grounded is False and answer is the server's
    own "insufficient context" message - no model call was made, but this
    still returns normally (it only raises RagError on an actual transport
    failure).
    """
    try:
        response = requests.post(
            f"{RAG_URL}/ask",
            json={
                "question": question,
                "context": context,
                "top_k": top_k,
                "max_tokens": max_tokens,
            },
            timeout=ASK_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise RagError(f"RAG server unreachable at {RAG_URL}: {exc}") from exc
    except ValueError as exc:
        raise RagError(f"RAG server returned a non-JSON response: {exc}") from exc


def search(question, top_k=4):
    """Retrieval only (no generation) - cheap way to check knowledge-base
    coverage without spending a model call."""
    try:
        response = requests.post(
            f"{RAG_URL}/search",
            json={"question": question, "top_k": top_k},
            timeout=SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise RagError(f"RAG server unreachable at {RAG_URL}: {exc}") from exc


def health():
    response = requests.get(f"{RAG_URL}/health", timeout=SEARCH_TIMEOUT)
    response.raise_for_status()
    return response.json()