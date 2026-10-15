"""Multi-agent workflow routes - student-1's Release 2 extension.

The frontend never talks to the shared Multi-Agent Server directly:

    Frontend -> student-1-api -> Multi-Agent Server
                                   -> Planner -> Worker -> Reviewer
                                   -> (waits) Human Review, submitted back
                                      through these same routes
             <- the released response, once a human decides

The Worker's evidence for a Trips & Itinerary task comes from student-1-db
through the shared MCP server, so the agents can only read what this feature's
MCP tools could read anyway.
"""

import re

import requests
from flask import Blueprint, request

from services import multi_agent_client
from views.agents import history_table, workflow_card, workflow_list
from views.formatters import ai_disabled_fragment, error_fragment

ai_agents_bp = Blueprint("ai_agents", __name__)

WORKFLOW_ID = re.compile(r"^wf-[A-Za-z0-9-]{1,60}$")
UNREACHABLE = (
    "It is not containerised - start it with ./scripts/ai_services.sh up"
)


def _guard(workflow_id):
    # The id is placed in a URL to the Multi-Agent Server, so only ever pass
    # one that has the shape the server issues.
    return bool(WORKFLOW_ID.match(workflow_id))


def _call(action):
    """Run one client call and turn every failure into a page fragment."""
    try:
        return action(), None
    except multi_agent_client.MultiAgentDisabled:
        return None, (ai_disabled_fragment("Multi-Agent"), 200)
    except multi_agent_client.MultiAgentError as exc:
        fragment = error_fragment("The Multi-Agent Server refused the request.", str(exc))
        if exc.workflow:
            fragment += workflow_card(exc.workflow)
        return None, (fragment, exc.status)
    except requests.RequestException as exc:
        return None, (
            error_fragment("Could not reach the shared Multi-Agent Server.",
                           f"{exc}\n\n{UNREACHABLE}"),
            503,
        )


@ai_agents_bp.post("/ai/agents")
def start():
    task = request.form.get("task", "").strip()
    trip_id = request.form.get("trip_id", "").strip()
    use_rag = request.form.get("use_rag") == "on"
    reviewer = request.form.get("reviewer", "").strip() or "student-1 page"

    if not task:
        return error_fragment("Describe the task for the agents first."), 400
    if len(task) > 1000:
        return error_fragment("Keep the task under 1,000 characters."), 400
    if trip_id and not trip_id.isdigit():
        return error_fragment("Trip ID must be a number."), 400

    # Offer the Planner the evidence this feature can legitimately provide.
    # It chooses which of these it needs; only those are fetched.
    if trip_id:
        mcp_calls = [{"tool": "get_trip_itinerary", "arguments": {"trip_id": int(trip_id)}}]
    else:
        mcp_calls = [{"tool": "list_trips", "arguments": {}}]

    workflow, failure = _call(lambda: multi_agent_client.start_workflow(
        task, mcp_calls, use_rag=use_rag, requested_by=f"student-1-ui:{reviewer}",
    ))
    if failure:
        return failure
    return workflow_card(workflow), 200


@ai_agents_bp.get("/ai/agents")
def recent():
    workflows, failure = _call(multi_agent_client.list_workflows)
    if failure:
        return failure
    return workflow_list(workflows), 200


@ai_agents_bp.get("/ai/agents/<workflow_id>")
def show(workflow_id):
    if not _guard(workflow_id):
        return error_fragment("That is not a workflow id."), 400
    workflow, failure = _call(lambda: multi_agent_client.get_workflow(workflow_id))
    if failure:
        return failure
    return workflow_card(workflow), 200


@ai_agents_bp.get("/ai/agents/<workflow_id>/history")
def history(workflow_id):
    if not _guard(workflow_id):
        return error_fragment("That is not a workflow id."), 400
    entries, failure = _call(lambda: multi_agent_client.get_history(workflow_id))
    if failure:
        return failure
    return history_table(entries), 200


@ai_agents_bp.post("/ai/agents/<workflow_id>/decision")
def decide(workflow_id):
    if not _guard(workflow_id):
        return error_fragment("That is not a workflow id."), 400

    decision = request.form.get("decision", "").strip()
    reviewer = request.form.get("reviewer", "").strip()
    comment = request.form.get("comment", "").strip()
    edited = request.form.get("final_response", "").strip()

    if not reviewer:
        return error_fragment("Enter your name so the decision is attributable."), 400

    # One comment box on the page. The server keeps feedback (instructions to
    # the Worker) separate from notes (the reason for a decision), so route it.
    feedback = comment if decision == "correct" else ""
    notes = "" if decision == "correct" else comment

    workflow, failure = _call(lambda: multi_agent_client.decide(
        workflow_id, decision, reviewer,
        notes=notes, feedback=feedback,
        final_response=edited if decision == "partial" else "",
    ))
    if failure:
        fragment, status = failure
        # A refused decision (missing notes, say) must not take the review form
        # off the page with it, so show the workflow again under the notice.
        if status in (400, 409):
            current, _ = _call(lambda: multi_agent_client.get_workflow(workflow_id))
            if current:
                fragment += workflow_card(current)
        return fragment, status
    return workflow_card(workflow), 200
