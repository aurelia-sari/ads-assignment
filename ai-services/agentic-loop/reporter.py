"""Terminal output and the markdown run record.

The markdown file under runs/ is the "Agentic Loop Workflow Record" the
technical report has to include, so it is written in a form that can be pasted
straight into docs/evidence.
"""

from datetime import datetime
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent / "runs"

STEP_COLOURS = {
    "PLAN": "\033[96m",
    "ACT": "\033[93m",
    "OBSERVE": "\033[95m",
    "ADAPT": "\033[92m",
}
RESET = "\033[0m"


def banner(text):
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def print_step(step, body):
    colour = STEP_COLOURS.get(step, "")
    print(f"\n{colour}[{step}]{RESET} {body}")


def print_menu():
    print(
        "\nReview target:\n"
        "  1  Database microservices\n"
        "  2  Backend/API implementation\n"
        "  3  Microservices architecture\n"
        "  4  DevOps pipeline\n"
        "  5  All four, in sequence\n"
        "  0  Exit"
    )


def write_run_record(iterations):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RUNS_DIR / f"agentic-loop-{stamp}.md"

    lines = [
        f"# Agentic loop run record - {stamp}",
        "",
        "Workflow: Plan -> Act -> Observe -> Adapt",
        "",
    ]
    for iteration in iterations:
        lines += [
            f"## Iteration {iteration.number} - {iteration.target}",
            f"_Started {iteration.started_at}_",
            "",
            "### Plan", "", iteration.plan, "",
            "### Act (evidence collected)", "", "```", iteration.evidence, "```", "",
            "### Observe", "", iteration.observations, "",
            "### Adapt", "", iteration.adaptation, "",
        ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
