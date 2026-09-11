"""Thin Ollama client for the agentic loop.

Uses the same OpenAI-compatible Ollama endpoint as the AI-Mode service, but
runs its own client so a review can use a larger review model than the one the
application serves to travellers.
"""

import os
from pathlib import Path

from openai import OpenAI

# The loop runs on the host in Release 1, so Ollama is on plain localhost.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_REVIEW_MODEL = os.getenv("OLLAMA_REVIEW_MODEL", OLLAMA_MODEL)


def _resolve_prompt_dir():
    """Find the shared prompt directory - see the note in ai-mode/app.py."""
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


def ask(system_prompt, user_prompt, max_tokens=400):
    response = client.chat.completions.create(
        model=OLLAMA_REVIEW_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()
