"""Client for the shared Multi-Agent Server (student-4, Aurelia Sari).

The server runs on the host, not in Docker, so the container reaches it through
host.docker.internal. CI and the cloud baseline set MULTI_AGENT_ENABLED=false.
"""

import os

import requests

MULTI_AGENT_URL = os.getenv("MULTI_AGENT_URL", "http://host.docker.internal:5600")
MULTI_AGENT_ENABLED = os.getenv("MULTI_AGENT_ENABLED", "true").lower() not in ("false", "0", "no")

FEATURE = "student-4"
RUN_TIMEOUT = 240
READ_TIMEOUT = 10


class MultiAgentDisabled(Exception):
    pass


class MultiAgentError(Exception):
    def __init__(self, message, status, workflow=None):
        super().__init__(message)
        self.status = status
        self.workflow = workflow


def _request(method, path, timeout, **kwargs):
    if not MULTI_AGENT_ENABLED:
        raise MultiAgentDisabled("Multi-Agent is disabled in this environment (MULTI_AGENT_ENABLED=false)")

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


def health():
    return _request("GET", "/health", 3)


def start_workflow(task, mcp_calls, evidence=None, requested_by=FEATURE):
    return _request("POST", "/workflows", RUN_TIMEOUT, json={
        "feature": FEATURE,
        "task": task,
        "mcp_calls": mcp_calls,
        "evidence": evidence or [],
        "requested_by": requested_by,
    })


def get_workflow(workflow_id):
    return _request("GET", f"/workflows/{workflow_id}", READ_TIMEOUT)


def list_workflows(limit=8):
    return _request("GET", "/workflows", READ_TIMEOUT, params={"feature": FEATURE, "limit": limit})["workflows"]


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
