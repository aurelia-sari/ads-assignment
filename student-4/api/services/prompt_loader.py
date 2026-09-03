from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(category, filename):
    return (PROMPT_DIR / category / filename).read_text(encoding="utf-8").strip()
