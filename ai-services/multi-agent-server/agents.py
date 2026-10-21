"""The Planner, Worker and Reviewer agents.

Each agent is one prompt plus the code that checks what comes back. None of
them talks to Ollama: every call goes through AI-Mode, so the team's standing
rule - only AI-Mode talks to the model - still holds in Release 2.

A 3B local model does not reliably return valid JSON, so the Planner and
Reviewer outputs are parsed defensively. When parsing fails the agent falls
back to a conservative default and says so in its output (`"source":
"fallback"`), rather than failing the workflow or pretending the model
produced something it did not. The fallback is always the cautious choice: a
plan that fetches every offered source, a review that reports concerns.

The Reviewer also runs deterministic checks alongside the model's review, for
the same reason the RAG server computes confidence from scores: a small model
asked to grade its own pipeline says "pass" almost unconditionally.
"""

import json
import os
import re
import time
from pathlib import Path

import requests

import evidence as evidence_module

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://localhost:5300")
TIMEOUT = int(os.getenv("MULTI_AGENT_LLM_TIMEOUT", "180"))
CLOUD_CITATION_VALIDATION = os.getenv("CLOUD_CITATION_VALIDATION", "false").lower() in (
    "true", "1", "yes",
)


class AgentError(Exception):
    """AI-Mode failed, or an enabled cloud citation check could not be satisfied."""


def _resolve_prompt_dir():
    """Find the shared prompt directory - see the note in ai-mode/app.py."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "prompts", here.parent / "prompts"):
        if candidate.is_dir():
            return candidate
    raise RuntimeError(f"No prompts directory found next to {here} or {here.parent}")


PROMPT_DIR = _resolve_prompt_dir()


def load_prompt(name):
    return (PROMPT_DIR / "multi-agent" / name).read_text(encoding="utf-8").strip()


def ask_ai_mode(system, content, max_tokens=500, timeout=None):
    try:
        response = requests.post(
            f"{AI_MODE_URL}/recommend",
            json={"system": system, "question": content, "max_tokens": max_tokens},
            timeout=TIMEOUT if timeout is None else timeout,
        )
        response.raise_for_status()
        body = response.json()
    except requests.RequestException as exc:
        raise AgentError(
            f"AI-Mode at {AI_MODE_URL} did not answer: {exc}. "
            "Start it with ./scripts/ai_services.sh up"
        ) from exc
    return body.get("answer", ""), body.get("model")


def extract_json(text):
    """The first JSON object in a model reply, or None.

    Models wrap JSON in prose or ``` fences often enough that json.loads on
    the raw reply fails most of the time.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _string_list(value, limit):
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


# --- Planner ----------------------------------------------------------------

def plan(feature, task, sources):
    source_list = "\n".join(f"{s['id']}: {s['label']}" for s in sources) or "(none)"
    content = (
        f"Feature: {feature}\n"
        f"Task: {task}\n\n"
        f"Evidence sources available:\n{source_list}"
    )
    raw, model = ask_ai_mode(load_prompt("planner_prompt.txt"), content, max_tokens=400)
    parsed = extract_json(raw) or {}

    valid_ids = {s["id"] for s in sources}
    required = [i for i in _string_list(parsed.get("required_evidence"), 20) if i in valid_ids]
    steps = _string_list(parsed.get("steps"), 5)
    criteria = _string_list(parsed.get("acceptance_criteria"), 4)
    goal = str(parsed.get("goal") or "").strip()

    if goal and steps and criteria and (required or not sources):
        return {
            "source": "model",
            "model": model,
            "goal": goal,
            "steps": steps,
            "required_evidence": required,
            "acceptance_criteria": criteria,
            "raw": raw,
        }

    return {
        "source": "fallback",
        "fallback_reason": "planner reply was not a usable JSON plan",
        "model": model,
        "goal": f"Answer the {feature} task using only the gathered evidence: {task}",
        "steps": [
            "Read every evidence item",
            "Answer the task using only facts found in the evidence",
            "State plainly anything the evidence does not cover",
        ],
        "required_evidence": [s["id"] for s in sources],
        "acceptance_criteria": [
            "Every factual claim cites an evidence item",
            "Gaps in the evidence are stated rather than filled in",
        ],
        "raw": raw,
    }


# --- Worker -----------------------------------------------------------------

def work(task, plan_, evidence, feedback=None, previous=None):
    content = (
        f"Task: {task}\n\n"
        f"Plan goal: {plan_['goal']}\n"
        "Plan steps:\n" + "\n".join(f"- {step}" for step in plan_["steps"]) + "\n\n"
        f"Evidence:\n{evidence_module.render(evidence)}\n\n"
    )
    if feedback:
        content += (
            f"Your previous response:\n{previous}\n\n"
            f"Human reviewer feedback to apply:\n{feedback}\n\n"
        )
    content += "Write the response now."

    system = load_prompt("worker_prompt.txt")
    if CLOUD_CITATION_VALIDATION:
        raw, model = _cloud_worker_response(system, content, evidence)
    else:
        # Keep the original local call contract, including existing test fakes.
        raw, model = ask_ai_mode(system, content, max_tokens=450)
    return {"model": model, "response": raw.strip(), "applied_feedback": feedback}


def _worker_citation_issues(response, evidence):
    risks = list(deterministic_checks(response, evidence)["risks"])
    # A response containing one valid reference and one combined reference must
    # not pass merely because the old single-reference regex found the first.
    groups = re.findall(r"\[([^\[\]\n]+)\]", response)
    malformed = [group for group in groups
                 if (re.search(r"\b[es]\s*\d", group, re.IGNORECASE)
                     or re.match(r"\s*\d", group))
                 and not re.fullmatch(r"E\d+", group)]
    if malformed:
        risks.append("Citations must each be one exact [E#] reference, not source IDs or combined IDs.")
    return risks


def _cloud_worker_response(system, content, evidence):
    """Require traceable cloud output, with at most one model-authored repair."""
    allowed = [item["id"] for item in evidence if item["ok"]]
    if not allowed:
        raise AgentError("No usable evidence is available for a grounded Worker response.")
    allowed_text = ", ".join(f"[{item}]" for item in allowed)
    rules = (
        "\n\nCloud citation validation: The ONLY permitted evidence citations are "
        f"{allowed_text}. Cite the enclosing evidence item's ID, never a row number "
        f"or an S# source ID. Every citation must use exactly one ID, such as [{allowed[0]}]; "
        "write separate references for separate items. Include at least one permitted "
        "citation and never cite an unavailable item. Preserve the task, evidence facts, "
        "required response format and any human feedback."
    )
    system += rules
    # Both generations share a single deadline. A CPU cloud must not turn one
    # failed response into two independent full-length model waits.
    deadline = time.monotonic() + min(TIMEOUT, 165)

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise AgentError("Worker citation validation exceeded its generation deadline.")
        return seconds

    raw, model = ask_ai_mode(system, content, max_tokens=450, timeout=remaining())
    remaining()
    if not isinstance(raw, str):
        raise AgentError("AI-Mode returned a non-text Worker response.")
    issues = _worker_citation_issues(raw, evidence)
    if not issues:
        return raw, model

    repair_content = (
        content + "\n\nAutomatic citation validation (not human feedback) rejected your previous response:\n"
        + raw + "\n\nProblems:\n- " + "\n- ".join(issues)
        + f"\n\nPermitted citations: {allowed_text}.\n"
        "Regenerate the complete answer from the original task, plan, evidence and human "
        "feedback above. Correct the citation problems using that evidence. Do not invent "
        "facts, evidence IDs or source mappings. Return only the complete corrected answer."
    )
    # Transport failures propagate immediately; they are not citation retries.
    repaired, model = ask_ai_mode(system, repair_content, max_tokens=450, timeout=remaining())
    remaining()
    if not isinstance(repaired, str):
        raise AgentError("AI-Mode returned a non-text Worker repair.")
    issues = _worker_citation_issues(repaired, evidence)
    if issues:
        raise AgentError("Worker citation validation failed after one repair: " + " ".join(issues))
    return repaired, model


# --- Reviewer ---------------------------------------------------------------

def deterministic_checks(response, evidence):
    """Checks that do not depend on the model's judgement of itself."""
    risks = []
    known_ids = {item["id"] for item in evidence}
    usable_ids = {item["id"] for item in evidence if item["ok"]}
    cited = set(re.findall(r"\[(E\d+)\]", response))

    if not usable_ids:
        risks.append("No evidence item was available, so the response cannot be grounded.")
    elif not cited:
        risks.append("The response cites no evidence items, so its claims cannot be traced.")

    unknown = sorted(cited - known_ids)
    if unknown:
        risks.append(f"The response cites evidence that does not exist: {', '.join(unknown)}.")

    unavailable = sorted(cited & (known_ids - usable_ids))
    if unavailable:
        risks.append(
            "The response cites evidence that was not available: "
            f"{', '.join(unavailable)}."
        )

    return {"cited": sorted(cited), "risks": risks}


def review(task, plan_, evidence, worker):
    criteria = "\n".join(f"- {c}" for c in plan_["acceptance_criteria"])
    content = (
        f"Task: {task}\n\n"
        f"Plan goal: {plan_['goal']}\n"
        f"Acceptance criteria:\n{criteria}\n\n"
        f"Evidence:\n{evidence_module.render(evidence)}\n\n"
        f"Worker response:\n{worker['response']}"
    )
    raw, model = ask_ai_mode(load_prompt("reviewer_prompt.txt"), content, max_tokens=500)
    parsed = extract_json(raw)
    checks = deterministic_checks(worker["response"], evidence)

    if parsed and parsed.get("verdict") in ("pass", "concerns", "fail"):
        verdict = parsed["verdict"]
        source = "model"
        criteria_results = [
            {
                "criterion": str(c.get("criterion", "")),
                "met": bool(c.get("met")),
                "note": str(c.get("note", "")),
            }
            for c in parsed.get("criteria") or []
            if isinstance(c, dict)
        ]
        risks = _string_list(parsed.get("risks"), 6)
        recommendations = _string_list(parsed.get("recommendations"), 6)
    else:
        verdict = "concerns"
        source = "fallback"
        criteria_results = []
        risks = ["The Reviewer's reply could not be parsed, so the response is unreviewed."]
        recommendations = ["Check the response against the evidence before approving it."]

    # A model "pass" never overrides a failed deterministic check.
    if checks["risks"] and verdict == "pass":
        verdict = "concerns"

    return {
        "source": source,
        "model": model,
        "verdict": verdict,
        "criteria": criteria_results,
        "risks": checks["risks"] + risks,
        "recommendations": recommendations,
        "checks": checks,
        "raw": raw,
    }
