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
import worker_tables

AI_MODE_URL = os.getenv("AI_MODE_URL", "http://localhost:5300")
TIMEOUT = int(os.getenv("MULTI_AGENT_LLM_TIMEOUT", "180"))
CLOUD_CITATION_VALIDATION = os.getenv("CLOUD_CITATION_VALIDATION", "false").lower() in (
    "true", "1", "yes",
)
CLOUD_STRUCTURED_OUTPUTS_ENABLED = os.getenv("CLOUD_STRUCTURED_OUTPUTS_ENABLED", "false").lower() in (
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


def ask_ai_mode(system, content, max_tokens=500, timeout=None, response_format=None):
    payload = {"system": system, "question": content, "max_tokens": max_tokens}
    if response_format is not None:
        payload["response_format"] = response_format
    try:
        response = requests.post(
            f"{AI_MODE_URL}/recommend",
            json=payload,
            timeout=TIMEOUT if timeout is None else timeout,
        )
        response.raise_for_status()
        body = response.json()
    except requests.RequestException as exc:
        if response_format is not None:
            detail = str(exc)
            failure = getattr(exc, "response", None)
            if failure is not None:
                try:
                    error = failure.json()
                except ValueError:
                    error = {}
                if isinstance(error, dict) and isinstance(error.get("detail"), str):
                    detail = error["detail"][:500]
            raise AgentError(f"AI-Mode structured generation failed: {detail}") from exc
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


def _structured_format(name, schema):
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}


def _validate_structured_value(value, schema):
    """Validate the schema subset used by Planner and Reviewer, without coercion."""
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(schema["required"]):
            return False
        return all(_validate_structured_value(value[key], child)
                   for key, child in schema["properties"].items())
    if kind == "array":
        return (isinstance(value, list) and schema.get("minItems", 0) <= len(value) <= schema["maxItems"]
                and all(_validate_structured_value(item, schema["items"]) for item in value))
    if kind == "string":
        return (isinstance(value, str) and schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", float("inf"))
                and ("enum" not in schema or value in schema["enum"]))
    if kind == "boolean":
        return type(value) is bool
    return False


def _structured_reply(raw, schema, agent):
    try:
        value = json.loads(raw) if isinstance(raw, str) else None
    except ValueError:
        value = None
    if not _validate_structured_value(value, schema):
        raise AgentError(f"{agent} structured generation returned invalid or incomplete JSON.")
    return value


def _planner_schema(sources):
    ids = [source["id"] for source in sources]
    reference = {"type": "string"}
    if ids:
        reference["enum"] = ids
    return {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "minLength": 1, "maxLength": 300},
            "steps": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 160},
                      "minItems": 1, "maxItems": 5},
            "required_evidence": {"type": "array", "items": reference,
                                  "minItems": 1 if ids else 0, "maxItems": len(ids)},
            "acceptance_criteria": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 200},
                                    "minItems": 1, "maxItems": 4},
        },
        "required": ["goal", "steps", "required_evidence", "acceptance_criteria"],
        "additionalProperties": False,
    }


# --- Planner ----------------------------------------------------------------

def plan(feature, task, sources):
    source_list = "\n".join(f"{s['id']}: {s['label']}" for s in sources) or "(none)"
    content = (
        f"Feature: {feature}\n"
        f"Task: {task}\n\n"
        f"Evidence sources available:\n{source_list}"
    )
    system = load_prompt("planner_prompt.txt")
    structured = CLOUD_CITATION_VALIDATION and CLOUD_STRUCTURED_OUTPUTS_ENABLED
    if structured:
        schema = _planner_schema(sources)
        system += "\n\nReturn only one complete JSON plan matching the supplied schema. Keep every field concise."
        content += "\n\nOutput JSON Schema:\n" + json.dumps(schema)
        raw, model = ask_ai_mode(system, content, max_tokens=900,
                                 response_format=_structured_format("grounded_planner", schema))
        parsed = _structured_reply(raw, schema, "Planner")
    else:
        raw, model = ask_ai_mode(system, content, max_tokens=400)
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

    if structured:
        raise AgentError("Planner structured generation returned no usable model plan.")
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
        raw, model = _cloud_worker_response(system, content, evidence, task=task)
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


def _worker_response_format(allowed, table=False, columns=None):
    # Use ordinary JSON strings, not a pattern over serialized string content:
    # regex character classes can consume JSON quotes in Ollama's grammar.
    # The model chooses the complete citation. Formatting that model-selected
    # reference never invents or remaps an evidence ID.
    if columns is not None:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "grounded_worker_table", "strict": True,
                "schema": worker_tables.response_schema(columns, allowed),
            },
        }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "grounded_worker_answer",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string", "minLength": 1, "maxLength": 2400 if table else 800,
                        "description": "The complete actual answer to the Task, not the task or plan itself.",
                    },
                    "citation": {
                        "type": "string", "enum": [f"[{item}]" for item in allowed],
                        "description": "The evidence item supporting the answer.",
                    },
                },
                "required": ["answer", "citation"],
                "additionalProperties": False,
            },
        },
    }


def _decode_worker_answer(raw, response_format, columns=None):
    if not isinstance(raw, str):
        return "", ["AI-Mode returned a non-text Worker response."]
    if response_format is None:
        return raw, []
    try:
        value = json.loads(raw)
    except ValueError:
        return "", ["Return one complete JSON object containing answer and citation strings."]
    if columns is not None:
        return worker_tables.decode_table(value, columns, response_format["json_schema"]["schema"])
    if not isinstance(value, dict) or set(value) != {"answer", "citation"} or not all(
            isinstance(value[field], str) for field in ("answer", "citation")):
        return "", ["Return exactly answer and citation strings."]
    properties = response_format["json_schema"]["schema"]["properties"]
    if value["citation"] not in properties["citation"]["enum"]:
        return "", ["The citation must be one complete permitted [E#] reference."]
    answer = value["answer"]
    if len(answer) > properties["answer"]["maxLength"]:
        return answer, ["Keep the response within the JSON Schema string length limit."]
    if not re.search(r"\w", re.sub(r"\[E\d+\]", "", answer)):
        return answer, ["Write a substantive response around the selected citation."]
    # Display the model's complete selected reference. Preserve its placement
    # when already present, and never replace or conceal other invalid IDs.
    if value["citation"] not in answer:
        answer = answer.rstrip() + " " + value["citation"]
    return answer, []


def _cloud_worker_response(system, content, evidence, task=""):
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
    # Tables carry several full records, while ordinary answers are short.
    # Bound each generated string to prevent repetition; allow enough output
    # tokens for the table without changing the shared generation deadline.
    columns = worker_tables.requested_columns(task) if CLOUD_STRUCTURED_OUTPUTS_ENABLED else None
    table = columns is not None or bool(re.search(r"\btable\b", task, re.IGNORECASE))
    response_format = _worker_response_format(allowed, table, columns) if CLOUD_STRUCTURED_OUTPUTS_ENABLED else None
    max_tokens = 1200 if response_format is not None and table else 450
    generation_options = {}
    if response_format is not None:
        generation_options["response_format"] = response_format
        system = (
            "You are the Worker in NextStop. Answer the original Task using ONLY its Evidence. "
            "The Task and human feedback override conflicting plan suggestions. Do not repeat "
            "instructions or analyse the plan. Never invent facts or recommend excluded records. "
            "Return one JSON object conforming to the supplied schema. "
            "In answer, give the actual recommendation or summary in one to three concise "
            "sentences, keeping any format explicitly requested by the Task. "
            "Do not repeat the task or describe tools, schemas or the plan. Include requested "
            "record identifiers and explain the choice using recorded facts. "
            "Choose the complete reference supporting the answer in citation; it is displayed "
            "with your answer. Do not invent personal preferences or claim a match to preferences "
            "that were not supplied. "
            "Copy requested record names, IDs, dates, opening hours and reasons exactly. "
            "Use Unknown only for a field absent from its evidence. Examples in the Task "
            "illustrate citation syntax, not which evidence supports a claim. "
            "Cite the enclosing evidence item, not an S# source or a row number. "
            "Use only the permitted references; unavailable evidence cannot support an answer. "
            "Human feedback, if included, must be applied without inventing facts."
        )
        if columns is not None:
            content_columns = [column for column in columns if column.strip().casefold()
                               not in worker_tables.CITATION_COLUMNS]
            system = (
                "You are the Worker in NextStop. Complete the original Task using ONLY its Evidence. "
                "Return a JSON rows array according to the schema. Each row has cells in this "
                f"exact order: {json.dumps(content_columns)}. Do not include the evidence column "
                "in cells: select that row's enclosing evidence reference in citation. "
                "The server formats these model-authored cells and citations as the requested "
                "Markdown table. Use one row per requested record. Copy all requested field values "
                "and full reasons exactly from the supplied evidence. Do not combine records, "
                "invent records, omit requested rows, or substitute Unknown for a supplied field. "
                "The original Task and human feedback override conflicting plan suggestions. "
                "Do not repeat instructions or explain the plan."
            )
        # Repeat the actual permitted choices in the system message. A syntax
        # example in a task can name an E ID that this plan did not retrieve.
        system += rules + (
            " Every further factual sentence also needs one of these references. "
            "Ignore citation examples naming an ID outside this permitted list."
        )
        content += "\n\nOutput JSON Schema:\n" + json.dumps(response_format["json_schema"]["schema"])
    # Async cloud Workers can have a longer budget without extending the
    # Planner, Reviewer or local calls. Both generations share this deadline.
    try:
        budget = int(os.getenv("CLOUD_WORKER_TIMEOUT_SECONDS", str(min(TIMEOUT, 165))))
    except ValueError as exc:
        raise AgentError("CLOUD_WORKER_TIMEOUT_SECONDS must be a positive integer.") from exc
    if budget <= 0:
        raise AgentError("CLOUD_WORKER_TIMEOUT_SECONDS must be a positive integer.")
    deadline = time.monotonic() + budget

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise AgentError("Worker citation validation exceeded its generation deadline.")
        return seconds

    raw, model = ask_ai_mode(system, content, max_tokens=max_tokens, timeout=remaining(), **generation_options)
    remaining()
    if not isinstance(raw, str) and response_format is None:
        raise AgentError("AI-Mode returned a non-text Worker response.")
    answer, issues = _decode_worker_answer(raw, response_format, columns)
    issues += _worker_citation_issues(answer, evidence)
    if not issues:
        return answer, model

    repair_content = (
        content + "\n\nAutomatic citation validation (not human feedback) rejected your previous response:\n"
        + str(raw) + "\n\nProblems:\n- " + "\n- ".join(issues)
        + f"\n\nPermitted citations: {allowed_text}.\n"
        "Regenerate the complete answer from the original task, plan, evidence and human "
        "feedback above. Correct the citation problems using that evidence. Do not invent "
        "facts, evidence IDs or source mappings. Return only the complete corrected answer."
    )
    # Transport failures propagate immediately; they are not citation retries.
    repaired, model = ask_ai_mode(system, repair_content, max_tokens=max_tokens, timeout=remaining(), **generation_options)
    remaining()
    if not isinstance(repaired, str):
        raise AgentError("AI-Mode returned a non-text Worker repair.")
    answer, issues = _decode_worker_answer(repaired, response_format, columns)
    issues += _worker_citation_issues(answer, evidence)
    if issues:
        raise AgentError("Worker citation validation failed after one repair: " + " ".join(issues))
    return answer, model


# --- Reviewer ---------------------------------------------------------------

def _reviewer_schema(criteria):
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 4 or any(
            not isinstance(criterion, str) or not criterion.strip() for criterion in criteria):
        raise AgentError("Reviewer structured generation needs 1-4 original acceptance criteria.")
    criterion_fields = {
        f"C{number}": {
            "type": "object", "properties": {
                "criterion": {"type": "string", "enum": [criterion]},
                "met": {"type": "boolean"},
                "note": {"type": "string", "maxLength": 100},
            }, "required": ["criterion", "met", "note"], "additionalProperties": False,
        } for number, criterion in enumerate(criteria, start=1)
    }
    return {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["pass", "concerns", "fail"]},
            "criteria": {"type": "object", "properties": criterion_fields,
                         "required": list(criterion_fields), "additionalProperties": False},
            "risks": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 140},
                      "minItems": 0, "maxItems": 6},
            "recommendations": {"type": "array", "items": {"type": "string", "minLength": 1, "maxLength": 140},
                                "minItems": 0, "maxItems": 6},
        }, "required": ["verdict", "criteria", "risks", "recommendations"], "additionalProperties": False,
    }

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
    options = {"max_tokens": 500}
    system = load_prompt("reviewer_prompt.txt")
    structured = CLOUD_CITATION_VALIDATION and CLOUD_STRUCTURED_OUTPUTS_ENABLED
    if structured:
        schema = _reviewer_schema(plan_["acceptance_criteria"])
        options.update(max_tokens=1200, response_format=_structured_format("grounded_reviewer", schema))
        system += (
            "\n\nReturn only one complete JSON review matching the supplied schema. Evaluate every "
            "original acceptance criterion in its assigned C# field exactly once. Keep notes, risks and recommendations concise. "
            "Give your actual verdict; do not change concerns or fail to pass."
        )
        content += "\n\nOutput JSON Schema:\n" + json.dumps(schema)
    # Only an explicitly configured cloud Reviewer extends its model wait.
    # Local calls keep the original timeout and the legacy function signature.
    reviewer_timeout = os.getenv("CLOUD_REVIEWER_TIMEOUT_SECONDS") if CLOUD_CITATION_VALIDATION else None
    if reviewer_timeout is not None:
        try:
            timeout = int(reviewer_timeout)
        except ValueError as exc:
            raise AgentError("CLOUD_REVIEWER_TIMEOUT_SECONDS must be a positive integer.") from exc
        if timeout <= 0:
            raise AgentError("CLOUD_REVIEWER_TIMEOUT_SECONDS must be a positive integer.")
        options["timeout"] = timeout
    raw, model = ask_ai_mode(system, content, **options)
    parsed = _structured_reply(raw, schema, "Reviewer") if structured else extract_json(raw)
    if structured:
        # Only reshape the model's checked fields; every criterion, met value
        # and note remains the original model output, in the plan's order.
        parsed = {**parsed, "criteria": [parsed["criteria"][key]
                                         for key in schema["properties"]["criteria"]["required"]]}
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
