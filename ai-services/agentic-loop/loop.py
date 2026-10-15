"""The shared team agentic workflow: Plan -> Act -> Observe -> Adapt.

One iteration runs all four steps against one review target and returns a
record of what happened. The ADAPT step feeds the next iteration, which is what
makes this a loop rather than a single review pass.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from collectors import COLLECTORS
from llm import load_prompt


@dataclass
class Iteration:
    number: int
    target: str
    plan: str = ""
    evidence: str = ""
    observations: str = ""
    adaptation: str = ""
    # Cloud Deployment Review only: the person who made the release call.
    release_decision: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def run_iteration(target_key, iteration_number, ask, on_step, carried_focus=""):
    description, review_prompt_file, collector = COLLECTORS[target_key]
    system_prompt = load_prompt("review/planner_system_prompt.txt")
    iteration = Iteration(number=iteration_number, target=description)

    # --- PLAN ------------------------------------------------------------
    on_step("PLAN", f"asking the model how to review {description}")
    plan_request = (
        f"{load_prompt('review/plan_prompt.txt')}\n\n"
        f"{load_prompt(review_prompt_file)}\n"
    )
    if carried_focus:
        plan_request += (
            f"\nThe previous iteration asked you to focus on this next:\n{carried_focus}\n"
        )
    iteration.plan = ask(system_prompt, plan_request, max_tokens=350)
    on_step("PLAN", iteration.plan)

    # --- ACT -------------------------------------------------------------
    on_step("ACT", "executing the plan against the running application")
    iteration.evidence = collector()
    on_step("ACT", iteration.evidence)

    # --- OBSERVE ---------------------------------------------------------
    on_step("OBSERVE", "comparing the plan against the collected evidence")
    # The review target's rules go to OBSERVE as well as PLAN: OBSERVE is where
    # the judging happens, and a mode's instructions (such as the cloud mode's
    # release recommendation) never reached it when only PLAN saw them.
    observe_request = (
        f"{load_prompt('review/observe_prompt.txt')}\n\n"
        f"REVIEW TARGET:\n{load_prompt(review_prompt_file)}\n\n"
        f"PLAN:\n{iteration.plan}\n\n"
        f"EVIDENCE:\n{iteration.evidence}\n"
    )
    iteration.observations = ask(system_prompt, observe_request, max_tokens=450)
    conflict = gate_conflict(iteration.evidence, iteration.observations)
    if conflict:
        iteration.observations += f"\n\n[loop] {conflict}"
    on_step("OBSERVE", iteration.observations)

    # --- ADAPT -----------------------------------------------------------
    on_step("ADAPT", "deciding the next change and the next check")
    adapt_request = (
        f"{load_prompt('review/adapt_prompt.txt')}\n\n"
        f"OBSERVATIONS:\n{iteration.observations}\n"
    )
    iteration.adaptation = ask(system_prompt, adapt_request, max_tokens=200)
    on_step("ADAPT", iteration.adaptation)

    return iteration


def release_gate(evidence):
    """The computed RELEASE GATE verdict (GO / NO-GO) in a mode's evidence, if any."""
    match = re.search(r"^RELEASE GATE: (NO-GO|GO)\b", evidence, re.M)
    return match.group(1) if match else None


def gate_conflict(evidence, observations):
    """A model recommendation that contradicts the computed gate is overruled.

    In trials the 3B review model recommended GO directly beneath a computed
    NO-GO with four failed requirements, so its recommendation is advice that
    the loop checks, never the verdict.
    """
    gate = release_gate(evidence)
    match = re.search(r"RELEASE RECOMMENDATION\W*\s*(NO-GO|GO)\b", observations)
    if not gate or not match or match.group(1) == gate:
        return ""
    return (
        f"The model recommended {match.group(1)}, which contradicts the computed "
        f"release gate ({gate}). The computed gate stands."
    )


def next_focus(iteration):
    """Pull the NEXT CHECK line out of the ADAPT output to seed the next PLAN."""
    for line in iteration.adaptation.splitlines():
        if line.strip().upper().startswith("NEXT CHECK"):
            return line.split(":", 1)[-1].strip()
    return ""
