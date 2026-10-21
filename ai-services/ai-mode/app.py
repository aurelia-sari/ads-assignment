"""Shared AI-Mode service.

One AI service for the whole team. Every student backend/API calls this service
instead of talking to Ollama itself, so the group has a single place for model
selection, prompt loading and error handling.

Request flow:  Frontend -> Backend/API -> AI-Mode -> Ollama -> LLM

As of Release 1 this runs on the host and is NOT a docker-compose service. The
containerised backends reach it through host.docker.internal, and it reaches
Ollama on plain localhost.

Run it with:  ./scripts/ai_services.sh up
"""

import os
import re
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# Running on the host now, so Ollama is on plain localhost. The
# host.docker.internal spelling only resolves from inside a container.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")


def _resolve_prompt_dir():
    """Find the shared prompt directory.

    The repo keeps prompts at ai-services/prompts, shared by AI-Mode and the
    agentic loop. The old container image copied them in alongside app.py
    instead, and the two layouts disagreeing is what broke the prompt path
    twice already. Checking both means neither layout can break it again.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here / "prompts", here.parent / "prompts"):
        if candidate.is_dir():
            return candidate
    raise RuntimeError(
        f"No prompts directory found next to {here} or {here.parent}"
    )


PROMPT_DIR = _resolve_prompt_dir()

client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")


def load_prompt(relative_path):
    return (PROMPT_DIR / relative_path).read_text(encoding="utf-8").strip()


def create_chat_completion(messages, max_tokens=300, temperature=0.2, model=None,
                           response_format=None):
    options = {
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format is not None:
        options.update(response_format=response_format, temperature=0)
    response = client.chat.completions.create(**options)
    if response_format is not None:
        if not response.choices:
            raise ValueError("Structured generation returned no completion.")
        choice = response.choices[0]
        if choice.finish_reason != "stop":
            raise ValueError(
                "Structured generation did not complete "
                f"(finish_reason={choice.finish_reason})."
            )
        if getattr(choice.message, "refusal", None):
            raise ValueError("Structured generation was refused by the model.")
        if not isinstance(choice.message.content, str) or not choice.message.content.strip():
            raise ValueError("Structured generation returned no text.")
    return response.choices[0].message.content.strip()


def _validate_response_format(value):
    """Check the optional transport envelope before sending it to Ollama."""
    if not isinstance(value, dict) or value.get("type") != "json_schema":
        raise ValueError("response_format must have type json_schema.")
    definition = value.get("json_schema")
    if not isinstance(definition, dict):
        raise ValueError("response_format.json_schema must be an object.")
    name = definition.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        raise ValueError("response_format.json_schema.name must be 1-64 letters, digits, underscores or hyphens.")
    schema = definition.get("schema")
    if not isinstance(schema, dict) or not schema:
        raise ValueError("response_format.json_schema.schema must be a nonempty object.")
    if "strict" in definition and type(definition["strict"]) is not bool:
        raise ValueError("response_format.json_schema.strict must be a boolean.")


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

    completion_options = {"max_tokens": max_tokens}
    if "response_format" in payload:
        try:
            _validate_response_format(payload["response_format"])
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        completion_options["response_format"] = payload["response_format"]

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
            **completion_options,
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
    app.run(host="0.0.0.0", port=int(os.getenv("AI_MODE_PORT", "5300")))  # noqa: S104 reached from containers through host.docker.internal
