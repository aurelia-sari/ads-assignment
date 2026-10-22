"""Agents endpoints for Travel Guides (student-4, Aurelia Sari).

    Frontend -> student-4-api -> Multi-Agent Server
                                   -> Planner -> Worker -> Reviewer
                                   -> (waits) Human Review, submitted back
                                      through these same routes

The Worker's evidence is the destination guide from student-4-db plus one MCP
lookup, so the agents only see what this feature could already read. Every
route returns an HTML fragment for HTMX, with a 200 for the disabled notice so
the page can still swap it in.
"""

import re

import requests
from flask import Blueprint, request

from agentic_loop.collectors.guide_collector import collect_destinations
from agentic_loop.core.classifier import extract_destination
from agentic_loop.core.orchestrator import no_city_message
from agentic_loop.pipelines.guide_chat_pipeline import gather_guide_facts
from services import multi_agent_client
from views.agents import history_table, workflow_card, workflow_list
from views.ai_formatter import error_fragment
from views.ai_tools_formatter import disabled_fragment, notice

ai_agents_bp = Blueprint("ai_agents", __name__)

WORKFLOW_ID = re.compile(r"^wf-[A-Za-z0-9-]{1,60}$")
MCP_TOOL = "lookup_destination_guide"
GUIDE_TOPICS = ("currency", "transport", "visa", "weather", "safety")
MAX_TASK_LENGTH = 800
MAX_CITY_LENGTH = 100
UNREACHABLE = "It is not containerised. Start it with ./scripts/ai_services.sh up"
BAD_WORKFLOW_ID = "That is not a workflow id."


def _guard(workflow_id):
    # The id is placed in a URL to the Multi-Agent Server, so only pass one shaped like its own.
    return bool(WORKFLOW_ID.match(workflow_id))


def _call(action):
    """Runs one client call and turns every failure into (None, (html, status))."""
    try:
        return action(), None
    except multi_agent_client.MultiAgentDisabled:
        return None, (disabled_fragment("Multi-Agent", "MULTI_AGENT_ENABLED"), 200)
    except multi_agent_client.MultiAgentError as exc:
        html = error_fragment("The Multi-Agent Server refused the request.", str(exc))
        if exc.workflow:
            html += workflow_card(exc.workflow)
        return None, (html, exc.status)
    except (requests.RequestException, ValueError) as exc:
        return None, (
            error_fragment("Could not reach the shared Multi-Agent Server.", f"{exc}\n\n{UNREACHABLE}"),
            503,
        )


def _guide_evidence(destination):
    """The guide facts the AI Assistant already uses, one evidence item per topic."""
    label = f"{destination['city']}, {destination['country']}"
    evidence = []
    for topic in GUIDE_TOPICS:
        context, _tokens, has_data = gather_guide_facts(topic, destination["id"])
        if has_data:
            evidence.append({"label": f"Travel guide {topic} for {label}", "content": context})
    return evidence


@ai_agents_bp.post("/ai/agents")
def start():
    task = request.form.get("task", "").strip()
    city = request.form.get("city", "").strip()
    use_rag = request.form.get("use_rag") == "on"
    reviewer = request.form.get("reviewer", "").strip() or "student-4 page"

    if not task:
        return notice("Describe the task for the agents first."), 400
    if len(task) > MAX_TASK_LENGTH:
        return notice(f"Keep the task under {MAX_TASK_LENGTH} characters."), 400
    if len(city) > MAX_CITY_LENGTH:
        return notice(f"Keep the city under {MAX_CITY_LENGTH} characters."), 400

    # A disabled server must not cost a database round trip.
    if not multi_agent_client.MULTI_AGENT_ENABLED:
        return disabled_fragment("Multi-Agent", "MULTI_AGENT_ENABLED"), 200

    # The City field wins, otherwise the city is read from the task like the AI Assistant does.
    try:
        destinations = collect_destinations()
        destination = extract_destination(city or task, destinations)
        evidence = _guide_evidence(destination) if destination else []
    except (requests.RequestException, ValueError) as exc:
        return error_fragment("Could not reach the Account & Dashboard database service.", exc), 503
    if not destination:
        return notice(no_city_message()), (404 if city else 400)

    agent_task = (
        f"{task} Answer for {destination['city']}, {destination['country']} using only the "
        "evidence, and cite the evidence id in square brackets, for example [E2]."
    )
    mcp_calls = [{"tool": MCP_TOOL, "arguments": {"query": destination["city"]}}]

    workflow, failure = _call(lambda: multi_agent_client.start_workflow(
        agent_task, mcp_calls, evidence=evidence, use_rag=use_rag, requested_by=f"student-4-ui:{reviewer}",
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
        return notice(BAD_WORKFLOW_ID), 400
    workflow, failure = _call(lambda: multi_agent_client.get_workflow(workflow_id))
    if failure:
        return failure
    return workflow_card(workflow), 200


@ai_agents_bp.get("/ai/agents/<workflow_id>/history")
def history(workflow_id):
    if not _guard(workflow_id):
        return notice(BAD_WORKFLOW_ID), 400
    entries, failure = _call(lambda: multi_agent_client.get_history(workflow_id))
    if failure:
        return failure
    return history_table(entries), 200


@ai_agents_bp.post("/ai/agents/<workflow_id>/decision")
def decide(workflow_id):
    if not _guard(workflow_id):
        return notice(BAD_WORKFLOW_ID), 400

    decision = request.form.get("decision", "").strip()
    reviewer = request.form.get("reviewer", "").strip()
    comment = request.form.get("comment", "").strip()
    edited = request.form.get("final_response", "").strip()

    if not reviewer:
        return notice("Enter your name so the decision is attributable."), 400

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
        html, status = failure
        # A refused decision must not take the review form off the page with it.
        if status in (400, 409):
            current, _ = _call(lambda: multi_agent_client.get_workflow(workflow_id))
            if current:
                html += workflow_card(current)
        return html, status
    return workflow_card(workflow), 200
