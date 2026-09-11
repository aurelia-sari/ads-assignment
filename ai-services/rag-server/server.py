"""Shared local RAG server for Group 25 (Release 1).

One non-containerised retrieval-augmented generation server on the host, used
by all five student features. Like the MCP server it is deliberately not a
docker-compose service; containerised backends reach it over
host.docker.internal.

Request flow:
    Frontend -> student-N-api -> RAG server -> AI-Mode -> Ollama -> LLM
                                     |
                                     +-> BM25 over knowledge/*.md

Generation goes through AI-Mode rather than straight to Ollama, so the team's
standing rule - only AI-Mode talks to the model - still holds in Release 1.

Every answer carries source citations and a confidence category. When retrieval
finds nothing relevant the server returns an insufficient-context response and
does not call the model at all, because the cheapest way to avoid an
unsupported answer is not to generate one.

Run it with:  ./scripts/ai_services.sh up
"""

import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from retriever import Index

app = Flask(__name__)
CORS(app)

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://localhost:5300")

# Retrieval thresholds. Calibrated against the curated corpus: a question the
# knowledge base genuinely covers scores well above the floor, and an
# off-corpus question ("what is the capital of Peru") scores at or near zero.
RELEVANCE_FLOOR = float(os.getenv("RAG_RELEVANCE_FLOOR", "2.5"))
HIGH_SCORE = float(os.getenv("RAG_HIGH_SCORE", "7.0"))
MEDIUM_SCORE = float(os.getenv("RAG_MEDIUM_SCORE", "4.0"))

TOP_K = int(os.getenv("RAG_TOP_K", "4"))

INSUFFICIENT_CONTEXT_ANSWER = (
    "I don't have enough information in the NextStop knowledge base to answer "
    "that. Nothing in the indexed travel or project documentation is relevant "
    "to this question, so I would be guessing rather than answering."
)

SYSTEM_PROMPT = (
    "You are the NextStop travel assistant. Answer using ONLY the numbered "
    "context passages provided. Do not add facts that are not in them. If the "
    "passages do not fully answer the question, say which part you cannot "
    "answer. Cite passages inline as you use them, like [1] or [2]. Do not "
    "add a citation list at the end - the citations are returned alongside "
    "your answer as structured data, so a trailing row of bare numbers is "
    "noise. Answer in at most four sentences."
)

index = Index()


def classify_confidence(hits):
    """Derive a confidence category from the retrieval evidence.

    Deliberately computed from scores rather than asked of the model. A small
    local model asked to rate its own confidence answers "high" almost
    unconditionally, which makes the field worthless exactly when it matters.

    Three signals: how strongly the best chunk matched, how much of the
    question that chunk covered, and whether anything else corroborated it.
    """
    if not hits:
        return "insufficient", "no chunk scored above zero"

    top = hits[0]
    supporting = [hit for hit in hits if hit["score"] >= RELEVANCE_FLOOR]

    if top["score"] < RELEVANCE_FLOOR:
        return "insufficient", (
            f"best score {top['score']} is below the relevance floor {RELEVANCE_FLOOR}"
        )

    if top["score"] >= HIGH_SCORE and top["coverage"] >= 0.5 and len(supporting) >= 2:
        return "high", (
            f"best score {top['score']} with {top['coverage']:.0%} question coverage, "
            f"corroborated by {len(supporting)} passages"
        )

    # Both signals are required, not either. Coverage alone promoted a weak
    # 2.7-scoring match to "medium" purely because it happened to touch half
    # the query terms, which is exactly the kind of overstated confidence the
    # category exists to prevent.
    if top["score"] >= MEDIUM_SCORE and top["coverage"] >= 0.4:
        return "medium", (
            f"best score {top['score']} with {top['coverage']:.0%} question coverage "
            f"from {len(supporting)} passage(s)"
        )

    return "low", (
        f"best score {top['score']} only just clears the relevance floor "
        f"{RELEVANCE_FLOOR}"
    )


def to_citation(hit, number):
    return {
        "number": number,
        "source": hit["source"],
        "section": hit["section"],
        "chunk": hit["chunk"],
        "score": hit["score"],
        "coverage": hit["coverage"],
        "excerpt": hit["text"][:240] + ("..." if len(hit["text"]) > 240 else ""),
    }


@app.get("/health")
def health():
    return jsonify(
        {
            "service": "rag-server",
            "status": "running",
            "containerised": False,
            "retrieval": "bm25",
            **index.stats(),
        }
    )


@app.get("/index")
def index_stats():
    return jsonify(index.stats())


@app.post("/reindex")
def reindex():
    """Rebuild the index after the knowledge base is edited, without a restart."""
    index.build()
    return jsonify({"reindexed": True, **index.stats()})


@app.post("/search")
def search():
    """Retrieval only, no generation. Used for terminal validation and by the
    agentic loop, which needs to check retrieval separately from grounding."""
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    top_k = int(payload.get("top_k", TOP_K))
    hits = index.search(question, top_k=top_k)
    confidence, reason = classify_confidence(hits)

    return jsonify(
        {
            "question": question,
            "confidence": confidence,
            "confidence_reason": reason,
            "hits": [to_citation(hit, number) for number, hit in enumerate(hits, start=1)],
        }
    )


@app.post("/ask")
def ask():
    """Retrieve, then generate a grounded answer with citations and confidence."""
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    # Feature backends may pass live application data alongside the question.
    # It is labelled separately from the retrieved passages so the model cannot
    # confuse a live row with a cited knowledge-base fact.
    live_context = (payload.get("context") or "").strip()
    top_k = int(payload.get("top_k", TOP_K))

    hits = index.search(question, top_k=top_k)
    confidence, reason = classify_confidence(hits)
    citations = [to_citation(hit, number) for number, hit in enumerate(hits, start=1)]

    if confidence == "insufficient":
        return jsonify(
            {
                "question": question,
                "grounded": False,
                "answer": INSUFFICIENT_CONTEXT_ANSWER,
                "confidence": "insufficient",
                "confidence_reason": reason,
                "citations": [],
                "model": None,
            }
        )

    passages = "\n\n".join(
        f"[{citation['number']}] ({citation['source']} > {citation['section']})\n"
        f"{hits[citation['number'] - 1]['text']}"
        for citation in citations
    )

    user_content = f"Context passages:\n{passages}\n\n"
    if live_context:
        user_content += (
            "Live application data (not a citable source, use only to resolve "
            f"what the traveller is referring to):\n{live_context}\n\n"
        )
    user_content += f"Question: {question}"

    try:
        response = requests.post(
            f"{AI_MODE_URL}/recommend",
            json={
                "question": user_content,
                "system": SYSTEM_PROMPT,
                "max_tokens": int(payload.get("max_tokens", 350)),
            },
            timeout=180,
        )
        response.raise_for_status()
        body = response.json()
    except requests.RequestException as exc:
        return (
            jsonify(
                {
                    "error": "RAG generation failed",
                    "detail": str(exc),
                    "hint": (
                        f"Retrieval succeeded ({len(citations)} passage(s)), but "
                        f"AI-Mode at {AI_MODE_URL} did not answer. Is it running? "
                        "Start it with ./scripts/ai_services.sh up"
                    ),
                    "citations": citations,
                }
            ),
            503,
        )

    return jsonify(
        {
            "question": question,
            "grounded": True,
            "answer": body.get("answer", ""),
            "confidence": confidence,
            "confidence_reason": reason,
            "citations": citations,
            "model": body.get("model"),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("RAG_PORT", "5500")))
