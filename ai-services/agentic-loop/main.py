"""Entry point for the shared team agentic loop.

    docker compose run --rm agentic-loop            interactive
    docker compose run --rm agentic-loop all 2      two iterations over all targets
"""

import sys

from llm import OLLAMA_BASE_URL, OLLAMA_REVIEW_MODEL, ask
from loop import next_focus, run_iteration
from reporter import banner, print_menu, print_step, write_run_record

TARGETS = {
    "1": "db",
    "2": "implementation",
    "3": "architecture",
    "4": "devops",
}
ALL_TARGETS = ["db", "implementation", "architecture", "devops"]


def run_targets(targets, iterations_per_target):
    records = []
    number = 0

    for target in targets:
        focus = ""
        for _ in range(iterations_per_target):
            number += 1
            banner(f"ITERATION {number} - target: {target}")
            iteration = run_iteration(target, number, ask, print_step, focus)
            records.append(iteration)
            focus = next_focus(iteration)

    path = write_run_record(records)
    banner(f"Run record written to {path}")
    return records


def main():
    banner("GROUP 25 AGENTIC LOOP - Plan -> Act -> Observe -> Adapt")
    print(f"Review model : {OLLAMA_REVIEW_MODEL}")
    print(f"Ollama       : {OLLAMA_BASE_URL}")

    argv = sys.argv[1:]
    if argv:
        target = argv[0]
        rounds = int(argv[1]) if len(argv) > 1 else 1
        targets = ALL_TARGETS if target == "all" else [target]
        run_targets(targets, rounds)
        return

    while True:
        print_menu()
        try:
            choice = input("> ").strip()
        except EOFError:
            print("\nNo terminal attached. Try: docker compose run --rm agentic-loop all 1")
            return

        if choice == "0":
            print("Loop closed.")
            return
        if choice == "5":
            run_targets(ALL_TARGETS, 1)
            continue
        if choice in TARGETS:
            run_targets([TARGETS[choice]], 1)
            continue

        print("Unrecognised choice.")


if __name__ == "__main__":
    main()
