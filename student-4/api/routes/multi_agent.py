"""Multi-Agent endpoints for Travel Guides (student-4, Aurelia Sari).

Planner, Worker and Reviewer run on the shared Multi-Agent Server and a person
decides at the end. Every route returns an HTML fragment for HTMX, with a 200
for the disabled notice so the page can still swap it in.
"""

import re

import requests
from flask import Blueprint, request

from agentic_loop.collectors.guide_collector import collect_destinations
from agentic_loop.core.classifier import extract_destination
from agentic_loop.core.orchestrator import no_city_message
from agentic_loop.pipelines.guide_chat_pipeline import gather_guide_facts
from services import multi_agent_client
from views import multi_agent_formatter as fmt

multi_agent_bp = Blueprint("multi_agent", __name__)

WORKFLOW_ID = re.compile(r"^wf-[A-Za-z0-9-]{1,60}$")
MCP_TOOL = "lookup_destination_guide"
GUIDE_TOPICS = ("currency", "transport", "visa", "weather", "safety")
MAX_CITY_LENGTH = 100
BAD_WORKFLOW_ID = "That is not a workflow id."


def _agent_call(action):
    """Runs one client call and turns every failure into (None, (html, status))."""
    try:
        return action(), None
    except multi_agent_client.MultiAgentDisabled:
        return None, (fmt.disabled_fragment(), 200)
    except multi_agent_client.MultiAgentError as exc:
        html = fmt.error_fragment("The Multi-Agent Server refused the request.", str(exc))
        if exc.workflow:
            html += fmt.workflow_card(exc.workflow)
        return None, (html, exc.status)
    except (requests.RequestException, ValueError) as exc:
        return None, (
            fmt.error_fragment(
                "Could not reach the shared Multi-Agent Server.",
                f"{exc}\n\nStart it with ./scripts/ai_services.sh up",
            ),
            503,
        )


def _guide_evidence(destination):
    """The guide facts the assistant already uses, one evidence item per topic."""
    label = f"{destination['city']}, {destination['country']}"
    evidence = []
    for topic in GUIDE_TOPICS:
        context, _tokens, has_data = gather_guide_facts(topic, destination["id"])
        if has_data:
            evidence.append({"label": f"Travel guide {topic} for {label}", "content": context})
    return evidence


@multi_agent_bp.post("/ai/multi-agent")
def multi_agent_start():
    city = request.form.get("city", "").strip()
    reviewer = request.form.get("reviewer", "").strip() or "student-4 page"

    if not city:
        return fmt.notice("Enter a city first."), 400
    if len(city) > MAX_CITY_LENGTH:
        return fmt.notice(f"Keep the city under {MAX_CITY_LENGTH} characters."), 400

    # A disabled server must not cost a database round trip.
    if not multi_agent_client.MULTI_AGENT_ENABLED:
        return fmt.disabled_fragment(), 200

    try:
        destination = extract_destination(city, collect_destinations())
        evidence = _guide_evidence(destination) if destination else []
    except (requests.RequestException, ValueError) as exc:
        return fmt.error_fragment("Could not reach the Account & Dashboard database service.", str(exc)), 503
    if not destination:
        return fmt.notice(no_city_message()), 404

    task = (
        f"Write a short pre-trip briefing for {destination['city']}, {destination['country']}. "
        "Cover currency, getting around, visa, weather and safety, using only the evidence, "
        "and cite the evidence id in square brackets, for example [E2]."
    )
    mcp_calls = [{"tool": MCP_TOOL, "arguments": {"query": destination["city"]}}]

    workflow, failure = _agent_call(lambda: multi_agent_client.start_workflow(
        task, mcp_calls, evidence=evidence, requested_by=f"student-4-ui:{reviewer}",
    ))
    if failure:
        return failure
    return fmt.workflow_card(workflow), 200


@multi_agent_bp.get("/ai/multi-agent")
def multi_agent_recent():
    workflows, failure = _agent_call(multi_agent_client.list_workflows)
    if failure:
        return failure
    return fmt.workflow_list(workflows), 200


@multi_agent_bp.get("/ai/multi-agent/<workflow_id>")
def multi_agent_show(workflow_id):
    if not WORKFLOW_ID.match(workflow_id):
        return fmt.notice(BAD_WORKFLOW_ID), 400
    workflow, failure = _agent_call(lambda: multi_agent_client.get_workflow(workflow_id))
    if failure:
        return failure
    return fmt.workflow_card(workflow), 200


@multi_agent_bp.get("/ai/multi-agent/<workflow_id>/history")
def multi_agent_history(workflow_id):
    if not WORKFLOW_ID.match(workflow_id):
        return fmt.notice(BAD_WORKFLOW_ID), 400
    entries, failure = _agent_call(lambda: multi_agent_client.get_history(workflow_id))
    if failure:
        return failure
    return fmt.history_table(entries), 200


@multi_agent_bp.post("/ai/multi-agent/<workflow_id>/decision")
def multi_agent_decide(workflow_id):
    if not WORKFLOW_ID.match(workflow_id):
        return fmt.notice(BAD_WORKFLOW_ID), 400
    decision = request.form.get("decision", "").strip()
    reviewer = request.form.get("reviewer", "").strip()
    comment = request.form.get("comment", "").strip()
    edited = request.form.get("final_response", "").strip()
    if not reviewer:
        return fmt.notice("Enter your name so the decision is attributable."), 400

    feedback = comment if decision == "correct" else ""
    notes = "" if decision == "correct" else comment
    workflow, failure = _agent_call(lambda: multi_agent_client.decide(
        workflow_id, decision, reviewer, notes=notes, feedback=feedback,
        final_response=edited if decision == "partial" else "",
    ))
    if failure:
        html, status = failure
        if status in (400, 409):
            # Show the workflow as it now stands, so a stale page can see what happened.
            current, _ = _agent_call(lambda: multi_agent_client.get_workflow(workflow_id))
            if current:
                html += fmt.workflow_card(current)
        return html, status
    return fmt.workflow_card(workflow), 200
