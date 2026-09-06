"""Thin Ollama client for the agentic loop.

Uses the same OpenAI-compatible Ollama endpoint as the AI-Mode service, but
runs its own client so a review can use a larger review model than the one the
application serves to travellers.
"""

import os
from pathlib import Path

from openai import OpenAI

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
OLLAMA_REVIEW_MODEL = os.getenv("OLLAMA_REVIEW_MODEL", OLLAMA_MODEL)

# The prompts sit in two different places depending on how the loop is run, and
# hard-coding either one breaks the other:
#   in the container, the Dockerfile copies them beside the modules -> /app/prompts
#   in the repo, they live one level up             -> ai-services/prompts
# Resolve by looking, so running it either way works.
_HERE = Path(__file__).resolve().parent
PROMPT_DIR = _HERE / "prompts" if (_HERE / "prompts").is_dir() else _HERE.parent / "prompts"

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
