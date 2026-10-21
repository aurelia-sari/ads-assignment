"""Student 5 gateway to the shared Multi-Agent Server; no agent logic runs here."""
import os

import requests


class MultiAgentError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def call(method, path, payload=None):
    if os.getenv("MULTI_AGENT_ENABLED", "true").lower() in ("false", "0", "no"):
        raise MultiAgentError(
            "Multi-Agent is disabled in this deployment (cloud default). "
            "It runs in the local deployment, where the shared Multi-Agent Server is available.",
            503,
        )
    url = os.getenv("MULTI_AGENT_URL", "http://host.docker.internal:5600").rstrip("/")
    try:
        response = requests.request(method, url + path, json=payload,
                                    timeout=240 if method == "POST" else 10)
    except requests.Timeout as exc:
        raise MultiAgentError("The Multi-Agent Server timed out. Refresh before retrying.", 504) from exc
    except requests.RequestException as exc:
        raise MultiAgentError("Could not reach the Multi-Agent Server. Start it with ./scripts/ai_services.sh up", 503) from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise MultiAgentError("The Multi-Agent Server returned invalid JSON.") from exc
    if response.status_code >= 400:
        raise MultiAgentError(str(body.get("error", "Request refused.")), response.status_code)
    return body
