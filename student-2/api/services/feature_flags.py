"""Local defaults stay enabled; deployment explicitly disables each integration."""
import os

FEATURES = {"ai": "AI_MODE_ENABLED", "mcp": "MCP_ENABLED",
            "rag": "RAG_ENABLED", "agents": "MULTI_AGENT_ENABLED"}


def disabled_feature(path):
    segment = path.strip("/").split("/", 1)[0]
    flag = FEATURES.get(segment)
    # Explicit enablement avoids treating a misspelled deployment value as true.
    if flag and os.getenv(flag, "true").strip().lower() not in ("true", "1", "yes", "on"):
        return flag
    return None
