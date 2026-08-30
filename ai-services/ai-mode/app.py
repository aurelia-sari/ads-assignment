"""Shared AI-Mode service.

One containerised AI service for the whole team. Every student backend/API
calls this service instead of talking to Ollama itself, so the group has a
single place for model selection, prompt loading and error handling.

Request flow:  Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM
"""

import os
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")


def load_prompt(relative_path):
    return (PROMPT_DIR / relative_path).read_text(encoding="utf-8").strip()


def create_chat_completion(messages, max_tokens=300, temperature=0.2, model=None):
    response = client.chat.completions.create(
        model=model or OLLAMA_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


@app.get("/health")
def health():
    return jsonify(
        {"service": "ai-mode", "status": "running", "model": OLLAMA_MODEL}
    )


@app.get("/model")
def model():
    """Reports whether the configured LLM is actually reachable."""
    try:
        create_chat_completion(
            [{"role": "user", "content": "Reply with the single word: ready"}],
            max_tokens=5,
        )
        return jsonify({"model": OLLAMA_MODEL, "reachable": True})
    except Exception as exc:
        return jsonify({"model": OLLAMA_MODEL, "reachable": False, "detail": str(exc)}), 503


@app.post("/chat")
def chat():
    """Generic chat entry point used by every student backend/API."""
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    system = payload.get("system") or load_prompt("implementation/system_prompt.txt")
    context = (payload.get("context") or "").strip()
    max_tokens = int(payload.get("max_tokens", 300))

    if not question:
        return jsonify({"error": "question is required"}), 400

    task_prompt = load_prompt("implementation/chatbot_task_prompt.txt")
    context_prompt = load_prompt("implementation/chatbot_context_prompt.txt")

    user_content = f"{task_prompt}\n\n{context_prompt}\n\n"
    if context:
        user_content += f"Live application data:\n{context}\n\n"
    user_content += f"Traveller question:\n{question}"

    try:
        answer = create_chat_completion(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=max_tokens,
        )
        return jsonify({"answer": answer, "model": OLLAMA_MODEL})
    except Exception as exc:
        return (
            jsonify(
                {
                    "error": "AI-Mode request failed",
                    "detail": str(exc),
                    "hint": (
                        f"Check Ollama is running and '{OLLAMA_MODEL}' is pulled: "
                        f"ollama pull {OLLAMA_MODEL}"
                    ),
                }
            ),
            503,
        )

@app.post("/recommend")
def recommend():
    payload = request.get_json(silent=True) or {}

    question = (payload.get("question") or "").strip()
    system = (payload.get("system") or "").strip()
    context = (payload.get("context") or "").strip()
    max_tokens = int(payload.get("max_tokens", 300))

    if not question:
        return jsonify({"error": "question is required"}), 400

    if not system:
        return jsonify({"error": "system is required"}), 400

    user_content = ""

    if context:
        user_content += f"Live application data:\n{context}\n\n"

    user_content += f"Traveller question:\n{question}"

    try:
        answer = create_chat_completion(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=max_tokens,
        )

        return jsonify({
            "answer": answer,
            "model": OLLAMA_MODEL
        })

    except Exception as exc:
        return (
            jsonify({
                "error": "AI recommendation request failed",
                "detail": str(exc),
            }),
            503,
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5300)
