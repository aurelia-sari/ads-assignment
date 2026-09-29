"""RAG tests for Student 2."""

import os

import requests


RAG_URL = os.getenv("RAG_URL", "http://localhost:5500")
API_URL = os.getenv("STUDENT2_API_URL", "http://localhost:5102")


def expect(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"  ok  {message}")


def post(base, path, payload=None, timeout=210):
    return requests.post(f"{base}{path}", json=payload or {}, timeout=timeout)


# Check the RAG answer fields
def validate_answer(body, prefix):
    required = {
        "question", "grounded", "answer", "confidence",
        "confidence_reason", "citations", "model",
    }
    expect(required <= set(body), f"{prefix} preserves the complete RAG contract")
    expect(body["grounded"] is True, f"{prefix} answer is grounded")
    expect(bool(body["answer"]), f"{prefix} answer is present")
    expect(body["confidence"] != "insufficient", f"{prefix} confidence is sufficient")
    expect(bool(body["citations"]), f"{prefix} citations are present")


# Run RAG checks
def run_checks():
    health = requests.get(f"{RAG_URL}/health", timeout=5)
    expect(health.status_code == 200, "shared RAG health returns 200")

    refreshed = post(RAG_URL, "/reindex")
    expect(refreshed.status_code == 200, "shared RAG reindex returns 200")
    expect(refreshed.json().get("reindexed") is True, "knowledge index is refreshed")

    query = "Sydney attractions and dining"
    searched = post(RAG_URL, "/search", {"question": query})
    expect(searched.status_code == 200, "shared RAG search returns 200")
    search_body = searched.json()
    expect(bool(search_body.get("hits")), "shared RAG returns relevant context")
    expect(bool(search_body.get("confidence_reason")), "search explains confidence")

    gateway_search = post(API_URL, "/rag/search", {"query": query})
    expect(gateway_search.status_code == 200, "Student 2 RAG search returns 200")
    expect(gateway_search.json() == search_body, "Student 2 preserves the search response")

    question = "What attractions and dining options are recommended in Sydney?"
    direct_answer = post(RAG_URL, "/ask", {"question": question})
    expect(direct_answer.status_code == 200, "shared RAG ask returns 200")
    validate_answer(direct_answer.json(), "shared RAG")

    gateway_answer = post(API_URL, "/rag/ask", {"question": question})
    expect(gateway_answer.status_code == 200, "Student 2 RAG ask returns 200")
    validate_answer(gateway_answer.json(), "Student 2")

    insufficient_question = "What is the capital of Peru?"
    insufficient = post(API_URL, "/rag/ask", {"question": insufficient_question})
    expect(insufficient.status_code == 200, "insufficient-context request returns safely")
    insufficient_body = insufficient.json()
    expect(insufficient_body.get("grounded") is False, "off-corpus answer is not grounded")
    expect(insufficient_body.get("confidence") == "insufficient", "confidence is insufficient")
    expect(insufficient_body.get("citations") == [], "off-corpus answer has no citations")
    expect("lima" not in insufficient_body.get("answer", "").lower(), "no invented Peru answer")

    gateway_reindex = post(API_URL, "/rag/reindex")
    expect(gateway_reindex.status_code == 200, "Student 2 reindex returns 200")
    expect(gateway_reindex.json().get("reindexed") is True, "Student 2 refreshes knowledge")

    expect(post(API_URL, "/rag/search", {"query": " "}).status_code == 400,
           "empty query returns 400")
    expect(post(API_URL, "/rag/ask", {"question": " "}).status_code == 400,
           "empty question returns 400")


if __name__ == "__main__":
    try:
        run_checks()
    except (AssertionError, KeyError, requests.RequestException) as exc:
        print(f"FAIL: {exc}")
        raise SystemExit(1)
    print("PASS: Student 2 RAG Release 1 checks completed.")
