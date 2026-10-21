"""Routes for the Bookings & Budget Agents tab (Planner -> Worker -> Reviewer -> Human)."""
import re

from flask import Blueprint, jsonify, request

from services import database_api
from services import multi_agent_client as client

agents_bp = Blueprint("agents", __name__)
WORKFLOW_ID = re.compile(r"wf-[A-Za-z0-9-]{1,60}")
DECISIONS = {"Accept": "approve", "Partially Accept": "partial", "Reject": "reject"}


@agents_bp.errorhandler(client.MultiAgentError)
def service_error(exc):
    return jsonify({"error": str(exc)}), exc.status


def _own_workflow(workflow_id):
    if not WORKFLOW_ID.fullmatch(workflow_id):
        raise client.MultiAgentError("Invalid workflow ID.", 400)
    body = client.call("GET", f"/workflows/{workflow_id}")
    if body.get("feature") != "student-5":
        raise client.MultiAgentError("This workflow does not belong to student-5.", 404)
    return body


def _evidence(trip_id):
    parts = []
    budget = database_api.get_budget(trip_id)
    if budget.ok:
        b = budget.json()
        parts.append(f"Budget for trip {trip_id} (AUD): total {b['total_budget']}, "
                     f"flights {b['flight_budget']}, hotels {b['hotel_budget']}.")
    selections = database_api.list_selections(trip_id)
    if selections:
        parts.append("Selections: " + "; ".join(
            f"{s['item_type']} {s['item_name']} ${s['price_aud']}" for s in selections) + ".")
        parts.append(f"Selected total: ${sum(float(s['price_aud']) for s in selections):.2f}.")
    else:
        parts.append("No flights or hotels are selected for this trip yet.")
    return [{"label": f"Bookings & Budget data for trip {trip_id}", "content": " ".join(parts)}]


@agents_bp.get("/agents/health")
def health():
    return jsonify(client.call("GET", "/health"))


@agents_bp.get("/agents/workflows")
def recent():
    body = client.call("GET", "/workflows?feature=student-5&limit=8")
    body["workflows"] = [w for w in body.get("workflows", []) if w.get("feature") == "student-5"]
    return jsonify(body)


@agents_bp.post("/agents/workflows")
def start():
    body = request.get_json(silent=True) or {}
    task = (body.get("task") or "").strip()
    trip_id = str(body.get("trip_id") or "1").strip()
    if not task or len(task) > 800:
        raise client.MultiAgentError("Enter a task of 1-800 characters.", 400)
    if not trip_id.isdigit():
        raise client.MultiAgentError("trip_id must be a number.", 400)
    result = client.call("POST", "/workflows", {
        "feature": "student-5", "task": task, "mcp_calls": [],
        "evidence": _evidence(int(trip_id)), "use_rag": False,
        "requested_by": "student-5-ui",
    })
    return jsonify(result), 201


@agents_bp.get("/agents/workflows/<workflow_id>")
def show(workflow_id):
    return jsonify(_own_workflow(workflow_id))


@agents_bp.get("/agents/workflows/<workflow_id>/history")
def history(workflow_id):
    _own_workflow(workflow_id)
    return jsonify(client.call("GET", f"/workflows/{workflow_id}/history"))


@agents_bp.post("/agents/workflows/<workflow_id>/decision")
def decide(workflow_id):
    body = request.get_json(silent=True) or {}
    label = (body.get("decision") or "").strip()
    reviewer = (body.get("reviewer") or "").strip()
    notes = (body.get("notes") or "").strip()
    if label not in DECISIONS:
        raise client.MultiAgentError("Choose Accept, Partially Accept or Reject.", 400)
    if not reviewer:
        raise client.MultiAgentError("Reviewer name is required.", 400)
    if label != "Accept" and not notes:
        raise client.MultiAgentError("Notes are required for Partially Accept or Reject.", 400)
    current = _own_workflow(workflow_id)
    if current["status"] != "awaiting_human_review":
        raise client.MultiAgentError("This workflow is not awaiting human review.", 409)
    result = client.call("POST", f"/workflows/{workflow_id}/decision", {
        "decision": DECISIONS[label], "reviewer": reviewer, "notes": notes,
        "final_response": (body.get("final_response") or "") if label == "Partially Accept" else "",
    })
    return jsonify(result)
