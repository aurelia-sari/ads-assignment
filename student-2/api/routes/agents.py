"""JSON routes used exclusively by the Attractions & Dining Agents tab."""
import re
from flask import Blueprint, jsonify, request
from routes.mcp import _text
from services import multi_agent_client as client
from services import place_evidence

agents_bp = Blueprint("agents", __name__)
WORKFLOW_ID = re.compile(r"wf-[A-Za-z0-9-]{1,60}")
DECISIONS = {"Accept": "approve", "Partially Accept": "partial", "Reject": "reject"}


@agents_bp.errorhandler(client.MultiAgentError)
def service_error(exc):
    body = {"error": str(exc)}
    if exc.workflow:
        body["workflow"] = exc.workflow
    return jsonify(body), exc.status


def payload():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise client.MultiAgentError("A JSON object is required.", 400)
    return body


def text(body, field, maximum, required=False):
    try:
        return _text(body.get(field), field, maximum, required)
    except ValueError as exc:
        raise client.MultiAgentError(str(exc), 400) from exc


def workflow(workflow_id):
    if not WORKFLOW_ID.fullmatch(workflow_id):
        raise client.MultiAgentError("Invalid workflow ID.", 400)
    return check_workflow(client.call("GET", f"/workflows/{workflow_id}"), workflow_id)


def check_workflow(body, expected_id=None):
    if body.get("feature") != "student-2":
        raise client.MultiAgentError("This workflow does not belong to student-2.", 404)
    wid = body.get("id")
    if not isinstance(wid, str) or not WORKFLOW_ID.fullmatch(wid) or (expected_id and wid != expected_id):
        raise client.MultiAgentError("Shared server returned an invalid workflow ID.")
    if not isinstance(body.get("status"), str):
        raise client.MultiAgentError("Shared server returned an invalid workflow status.")
    body["student2_validation"] = place_evidence.validate(body)
    if body.get("final_response"):
        body["student2_final_validation"] = place_evidence.validate(body, body["final_response"])
    return body


@agents_bp.get("/agents/health")
def health():
    return jsonify(client.call("GET", "/health"))


@agents_bp.get("/agents/workflows")
def recent():
    body = client.call("GET", "/workflows?feature=student-2&limit=8")
    if not isinstance(body.get("workflows"), list):
        raise client.MultiAgentError("Shared server returned an invalid workflow list.")
    body["workflows"] = [w for w in body["workflows"] if isinstance(w, dict) and w.get("feature") == "student-2"]
    return jsonify(body)


@agents_bp.post("/agents/workflows")
def start():
    body = payload()
    task = text(body, "task", 1000, True)
    category = place_evidence.task_category(task, text(body, "category", 40))
    name = text(body, "name", 60)
    if category not in ("all", "attraction", "restaurant", "activity"):
        raise client.MultiAgentError("Choose all, attraction, restaurant or activity.", 400)
    city = place_evidence.task_city(task, text(body, "city", 40))
    required = place_evidence.required_categories(task, category)
    remaining = 1000 - len(place_evidence.instruction("", city, required))
    task = place_evidence.instruction(task, city, required)
    if len(task) > 1000:
        raise client.MultiAgentError(f"Shorten the request to {remaining} characters to leave room for evidence instructions.", 400)
    categories = ("attraction", "restaurant", "activity") if category == "all" else (category,)
    # MCP is called here, then only compact city-filtered records are supplied.
    # Sending broad mcp_calls to the shared server would reintroduce other cities.
    categories = tuple(dict.fromkeys((*categories, *required)))
    evidence = place_evidence.collect(city, categories, name, required)
    result = client.call("POST", "/workflows", {
        "feature": "student-2", "task": task, "mcp_calls": [],
        "evidence": evidence, "use_rag": False, "requested_by": "student-2-ui",
    })
    return jsonify(check_workflow(result)), 201


@agents_bp.get("/agents/workflows/<workflow_id>")
def show(workflow_id):
    return jsonify(workflow(workflow_id))


@agents_bp.get("/agents/workflows/<workflow_id>/history")
def history(workflow_id):
    workflow(workflow_id)  # Enforce the feature boundary before exposing its log.
    return jsonify(client.call("GET", f"/workflows/{workflow_id}/history"))


@agents_bp.post("/agents/workflows/<workflow_id>/decision")
def decide(workflow_id):
    body = payload()
    decision = text(body, "decision", 40, True)
    reviewer = text(body, "reviewer", 100, True)
    notes = text(body, "notes", 2000, decision in ("Partially Accept", "Reject"))
    if decision not in DECISIONS:
        raise client.MultiAgentError("Choose Accept, Partially Accept or Reject.", 400)
    edited = text(body, "final_response", 12000)
    current = workflow(workflow_id)
    if current["status"] != "awaiting_human_review":
        raise client.MultiAgentError("This workflow is not awaiting human review.", 409)
    if decision != "Reject":
        report = place_evidence.validate(current, edited if decision == "Partially Accept" and edited else None)
        if not report["can_accept"]:
            raise client.MultiAgentError("Place validation found issues. Reject this answer or use Partially Accept with a corrected place table. " + " ".join(report["issues"]), 422, current)
    result = client.call("POST", f"/workflows/{workflow_id}/decision", {
        "decision": DECISIONS[decision], "reviewer": reviewer, "notes": notes,
        "final_response": edited if decision == "Partially Accept" else "",
    })
    return jsonify(check_workflow(result, workflow_id))
