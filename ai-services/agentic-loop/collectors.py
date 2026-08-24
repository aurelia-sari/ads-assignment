"""ACT step: collect real evidence from the running application and the repo.

Nothing here asks the LLM anything. These functions make live HTTP calls and
read files, so that the OBSERVE step reviews facts rather than assumptions.
"""

import json
import os
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(os.getenv("REPO_ROOT", "/repo"))

STUDENTS = [
    ("student-1", "Trips & Itinerary",     5101, 5201, ["/trips", "/days"]),
    ("student-2", "Attractions & Dining",  5102, 5202, ["/records"]),
    ("student-3", "Travel Mate",           5103, 5203, ["/records"]),
    ("student-4", "Account & Dashboard",   5104, 5204, ["/records"]),
    ("student-5", "Bookings & Budget",     5105, 5205, ["/records"]),
]


def _get(url, timeout=4):
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code, response
    except requests.RequestException as exc:
        return None, str(exc)


def _read(relative_path):
    path = REPO_ROOT / relative_path
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def collect_database_evidence():
    lines = []
    for name, feature, _api_port, db_port, resources in STUDENTS:
        base = f"http://{name}-db:{db_port}"
        status, response = _get(f"{base}/health")
        if status != 200:
            lines.append(f"{name}-db: UNREACHABLE ({response})")
            continue

        lines.append(f"{name}-db: health 200 ({feature})")
        for resource in resources:
            status, response = _get(f"{base}{resource}")
            if status != 200:
                lines.append(f"  GET {resource}: status {status}")
                continue
            try:
                rows = response.json()
                count = len(rows) if isinstance(rows, list) else "n/a"
                sample = json.dumps(rows[0], sort_keys=True) if isinstance(rows, list) and rows else "{}"
                lines.append(f"  GET {resource}: 200, {count} rows, columns={sample[:180]}")
            except ValueError:
                lines.append(f"  GET {resource}: 200 but response was not JSON")
    return "\n".join(lines)


def collect_implementation_evidence():
    lines = []
    for name, feature, api_port, _db_port, _resources in STUDENTS:
        status, response = _get(f"http://{name}-api:{api_port}/health")
        state = "200" if status == 200 else f"{status or 'unreachable'} ({response if status is None else ''})"
        lines.append(f"{name}-api ({feature}): health {state}")

    status, response = _get("http://ai-mode:5300/health")
    lines.append(f"ai-mode: health {status or 'unreachable'}")
    if status == 200:
        lines.append(f"  configured model: {response.json().get('model')}")

    status, response = _get("http://ai-mode:5300/model", timeout=90)
    if status == 200:
        lines.append("  LLM reachable: yes")
    else:
        detail = response if isinstance(response, str) else response.text[:160]
        lines.append(f"  LLM reachable: NO -> {detail}")

    return "\n".join(lines)


def collect_architecture_evidence():
    compose = _read("docker-compose.yml") or ""
    nginx = _read("shared/nginx.conf") or ""

    parsed = yaml.safe_load(compose) if compose else {}
    services = parsed.get("services", {})
    profiled = {
        name for name, spec in services.items()
        if isinstance(spec, dict) and spec.get("profiles")
    }
    default_services = [name for name in services if name not in profiled]

    routed = [line.strip() for line in nginx.splitlines() if "proxy_pass" in line]

    status, response = _get("http://shared-api:5000/health/all", timeout=30)
    health_fragment = response.text[:400] if status == 200 else f"shared-api unreachable ({status})"

    return (
        f"docker-compose.yml declares {len(services)} services, "
        f"{len(default_services)} of which start by default "
        f"(profile-gated: {', '.join(sorted(profiled)) or 'none'}):\n"
        + "\n".join(f"  - {name}" for name in services)
        + f"\n\nshared/nginx.conf declares {len(routed)} proxy routes:\n"
        + "\n".join(f"  {route}" for route in routed)
        + f"\n\nLive health fragment from shared-api:\n{health_fragment}"
    )


def collect_devops_evidence():
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    if not workflow_dir.exists():
        return "No .github/workflows directory found."

    lines = []
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        steps = text.count("      - name:")
        # The workflows build through compose, so count both spellings.
        builds = text.count("docker compose build") + text.count("docker build")
        lines.append(
            f"{path.name}: {len(text.splitlines())} lines, "
            f"{builds} compose-build step(s), {steps} named step(s), triggers on "
            f"{'pull_request' if 'pull_request' in text else 'push only'}"
        )

    compose = _read("docker-compose.yml") or ""
    lines.append(f"docker-compose.yml present: {bool(compose)} ({len(compose.splitlines())} lines)")
    return "\n".join(lines)


COLLECTORS = {
    "db": ("the database microservices", "review/database_review_prompt.txt", collect_database_evidence),
    "implementation": ("the backend/API implementation", "review/implementation_review_prompt.txt", collect_implementation_evidence),
    "architecture": ("the microservices architecture", "review/architecture_review_prompt.txt", collect_architecture_evidence),
    "devops": ("the DevOps pipeline", "review/devops_review_prompt.txt", collect_devops_evidence),
}
