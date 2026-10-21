"""Runtime switches for the shared AI services.

The cloud deployment keeps AI-Mode, MCP, RAG and Multi-Agent disabled by
default (docker-compose passes AI_MODE_ENABLED=false etc.). Locally they
default to enabled.
"""

import os


def _enabled(name):
    return os.getenv(name, "true").strip().lower() == "true"


AI_MODE_ENABLED = _enabled("AI_MODE_ENABLED")
MCP_ENABLED = _enabled("MCP_ENABLED")
RAG_ENABLED = _enabled("RAG_ENABLED")


def disabled_message(service):
    return (
        f"{service} is disabled in this deployment (cloud default). "
        "It runs in the local deployment, where the shared AI services are available."
    )
