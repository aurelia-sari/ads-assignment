from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(category, filename):
    prompt_path = PROMPT_DIR / category / filename

    return prompt_path.read_text(encoding="utf-8")