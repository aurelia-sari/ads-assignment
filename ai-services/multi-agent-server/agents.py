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
from pathlib import Path

import requests

import evidence as evidence_module

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://localhost:5300")
TIMEOUT = int(os.getenv("MULTI_AGENT_LLM_TIMEOUT", "180"))


class AgentError(Exception):
    """AI-Mode could not be reached or did not answer."""


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


def ask_ai_mode(system, content, max_tokens=500):
    try:
        response = requests.post(
            f"{AI_MODE_URL}/recommend",
            json={"system": system, "question": content, "max_tokens": max_tokens},
            timeout=TIMEOUT,
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

    raw, model = ask_ai_mode(load_prompt("worker_prompt.txt"), content, max_tokens=450)
    return {"model": model, "response": raw.strip(), "applied_feedback": feedback}


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
