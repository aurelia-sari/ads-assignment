"""Client for the shared Multi-Agent Server (Release 2).

student-1-api does not run agents itself. It asks the one shared Multi-Agent
Server to run Planner -> Worker -> Reviewer, then relays the human reviewer's
decision back to it. The server keeps the workflow state and the audit log, so
a workflow started from this page and one started from the terminal leave the
same trail.

Like MCP and RAG the server is not containerised, so in Docker it is reached
through host.docker.internal, and MULTI_AGENT_ENABLED=false (as in CI) skips
the runtime path rather than waiting out a timeout against nothing.
"""

import os

import requests

MULTI_AGENT_URL = os.getenv("MULTI_AGENT_URL", "http://host.docker.internal:5600")
MULTI_AGENT_ENABLED = os.getenv("MULTI_AGENT_ENABLED", "true").lower() not in (
    "false", "0", "no",
)

# A run is three model calls, and a correction is two more. The nginx proxies
# in front of this API allow 300 s, so stay under that.
RUN_TIMEOUT = 240
READ_TIMEOUT = 10


class MultiAgentDisabled(Exception):
    """Raised when the Multi-Agent Server is switched off, as it is in CI."""


class MultiAgentError(Exception):
    """The server answered with an error. Carries its message and any workflow."""

    def __init__(self, message, status, workflow=None):
        super().__init__(message)
        self.status = status
        self.workflow = workflow


def _request(method, path, timeout, **kwargs):
    if not MULTI_AGENT_ENABLED:
        raise MultiAgentDisabled(
            "the Multi-Agent Server is disabled in this environment (MULTI_AGENT_ENABLED=false)"
        )

    response = requests.request(method, f"{MULTI_AGENT_URL}{path}", timeout=timeout, **kwargs)
    try:
        body = response.json()
    except ValueError:
        response.raise_for_status()
        raise

    if response.status_code >= 400:
        message = body.get("error", f"HTTP {response.status_code}")
        if body.get("detail"):
            message += f": {body['detail']}"
        raise MultiAgentError(message, response.status_code, body.get("workflow"))
    return body


def start_workflow(task, mcp_calls, evidence=None, use_rag=True, requested_by="student-1"):
    return _request("POST", "/workflows", RUN_TIMEOUT, json={
        "feature": "student-1",
        "task": task,
        "mcp_calls": mcp_calls,
        "evidence": evidence or [],
        "use_rag": use_rag,
        "requested_by": requested_by,
    })


def get_workflow(workflow_id):
    return _request("GET", f"/workflows/{workflow_id}", READ_TIMEOUT)


def list_workflows(limit=8):
    return _request(
        "GET", "/workflows", READ_TIMEOUT, params={"feature": "student-1", "limit": limit}
    )["workflows"]


def get_history(workflow_id):
    return _request("GET", f"/workflows/{workflow_id}/history", READ_TIMEOUT)["history"]


def decide(workflow_id, decision, reviewer, notes="", feedback="", final_response=""):
    return _request("POST", f"/workflows/{workflow_id}/decision", RUN_TIMEOUT, json={
        "decision": decision,
        "reviewer": reviewer,
        "notes": notes,
        "feedback": feedback,
        "final_response": final_response,
    })
