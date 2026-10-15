"""Student 2 gateway to the shared Release 2 server; no local agent execution."""
import os
import requests


class MultiAgentError(Exception):
    def __init__(self, message, status=502, workflow=None):
        super().__init__(message)
        self.status = status
        self.workflow = workflow


def call(method, path, payload=None):
    if os.getenv("MULTI_AGENT_ENABLED", "true").lower() in ("false", "0", "no"):
        raise MultiAgentError("Multi-Agent is disabled (MULTI_AGENT_ENABLED=false).", 503)
    url = os.getenv("MULTI_AGENT_URL", "http://host.docker.internal:5600").rstrip("/")
    try:
        response = requests.request(method, url + path, json=payload,
                                    timeout=240 if method == "POST" else 10)
    except requests.Timeout as exc:
        raise MultiAgentError(
            "Shared Multi-Agent timed out. The server may still be processing; refresh recent workflows before retrying.", 504
        ) from exc
    except requests.RequestException as exc:
        raise MultiAgentError("Could not reach the shared Multi-Agent server. Check its local service and MULTI_AGENT_URL.", 503) from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise MultiAgentError("Shared Multi-Agent returned invalid JSON.") from exc
    if not isinstance(body, dict):
        raise MultiAgentError("Shared Multi-Agent returned an invalid response.")
    if response.status_code >= 400:
        message = str(body.get("error", "Shared Multi-Agent refused the request."))
        if body.get("detail"):
            message += ": " + str(body["detail"])
        workflow = body.get("workflow")
        if not isinstance(workflow, dict) or workflow.get("feature") != "student-2":
            workflow = None
        raise MultiAgentError(message, response.status_code, workflow)
    return body
