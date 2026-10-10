"""Entry point for the shared team agentic loop.

Runs on the host - Release 1 requires the loop to be non-containerised.

    ./scripts/dev.sh loop             interactive
    ./scripts/dev.sh loop all 2       two iterations over every target
    ./scripts/dev.sh loop mcp         the MCP validation mode alone
    ./scripts/dev.sh loop rag         the RAG validation mode alone
    ./scripts/dev.sh loop multiagent  Release 2: Multi-Agent Workflow Review
    ./scripts/dev.sh loop testing     Release 2: Testing Review
    ./scripts/dev.sh loop cloud       Release 2: Cloud Deployment Review, ending
                                      with the human release decision
"""

import getpass
import sys
from datetime import datetime

from llm import OLLAMA_BASE_URL, OLLAMA_REVIEW_MODEL, ask
from loop import next_focus, release_gate, run_iteration
from reporter import banner, print_menu, print_step, write_run_record

TARGETS = {
    "1": "db",
    "2": "implementation",
    "3": "architecture",
    "4": "devops",
    "5": "mcp",
    "6": "rag",
    "7": "multiagent",
    "8": "testing",
    "9": "cloud",
}
ALL_TARGETS = [
    "db", "implementation", "architecture", "devops", "mcp", "rag",
    "multiagent", "testing", "cloud",
]


def ask_release_decision(iteration):
    """The Cloud Deployment Review ends with a person deciding, not the model.

    The model's RELEASE RECOMMENDATION is advice. The decision recorded in the
    run record is the human's, with their name and reason, so the report can
    show who released what and on what evidence.
    """
    if not sys.stdin.isatty():
        iteration.release_decision = (
            f"NOT RECORDED - no terminal attached (computed release gate: "
            f"{release_gate(iteration.evidence) or 'not computed'}). Re-run "
            "./scripts/dev.sh loop cloud interactively to record the release decision."
        )
        return

    gate = release_gate(iteration.evidence) or "not computed"
    banner("HUMAN RELEASE DECISION")
    print("The review above is advice. The release decision is yours.")
    print(f"Computed release gate: {gate}")
    while True:
        choice = input("Release? [g]o / [n]o-go / [d]efer > ").strip().lower()[:1]
        if choice in ("g", "n", "d"):
            break
    decision = {"g": "GO", "n": "NO-GO", "d": "DEFERRED"}[choice]
    name = input(f"Your name [{getpass.getuser()}] > ").strip() or getpass.getuser()
    reason = ""
    while not reason:
        reason = input("Reason (required) > ").strip()
    stamp = datetime.now().isoformat(timespec="seconds")
    override = " OVERRIDES the computed NO-GO gate." if decision == "GO" and gate == "NO-GO" else ""
    iteration.release_decision = (
        f"{decision} - decided by {name} at {stamp} (computed release gate: {gate}).{override} "
        f"Reason: {reason}"
    )
    print_step("DECISION", iteration.release_decision)


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
        if target == "cloud":
            ask_release_decision(records[-1])

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
            print("\nNo terminal attached. Try: ./scripts/dev.sh loop all 1")
            return

        if choice == "0":
            print("Loop closed.")
            return
        if choice == "10":
            run_targets(ALL_TARGETS, 1)
            continue
        if choice in TARGETS:
            run_targets([TARGETS[choice]], 1)
            continue

        print("Unrecognised choice.")


if __name__ == "__main__":
    main()
