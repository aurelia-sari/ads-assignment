"""ACT step for the Release 2 review modes.

Three modes, each reviewing the evidence the Release 2 brief names:

  multiagent  Multi-Agent Workflow Review - the live workflows and their audit
              logs on the shared Multi-Agent Server
  testing     Testing Review - pre-commit security scans and each student's
              post-commit endpoint tests in student-x.yml
  cloud       Cloud Deployment Review - cloud-deployment.yml, the deployment
              scripts, and the deployed application itself

Like the Release 1 collectors, nothing here asks the model anything. Where
the brief sets a rule, the collector decides in code whether it held and puts
that verdict in a CHECK RESULTS block at the top of the evidence, with the
detail underneath. The first trial run showed why: given only the detail, the
3B review model reported the server as containerised when the evidence said
the opposite, and called seven listed probe results "not shown". A verdict
computed in code is a fact the model can rank and explain but not invert.
"""

import json
import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(os.getenv("REPO_ROOT", Path(__file__).resolve().parents[2]))
MULTI_AGENT_URL = os.getenv("MULTI_AGENT_URL", "http://localhost:5600")
STUDENT_NUMBERS = range(1, 6)
FINAL_STATUSES = ("approved", "partially_accepted", "rejected")


class Checks:
    """PASS / FAIL / WARN verdicts, reported ahead of the detail they come from."""

    def __init__(self):
        self.rows = []

    def add(self, ok, text, warn=False):
        self.rows.append(("PASS" if ok else "WARN" if warn else "FAIL", text))

    def report(self, detail, release_gate=False):
        counts = {k: sum(1 for s, _ in self.rows if s == k) for k in ("PASS", "FAIL", "WARN")}
        head = [
            "CHECK RESULTS (decided in code from the detail below - treat them as "
            f"established facts): {counts['PASS']} PASS, {counts['FAIL']} FAIL, "
            f"{counts['WARN']} WARN"
        ]
        if release_gate:
            # The gate is advice for the human release decision, computed so
            # that the model cannot recommend GO over a failed requirement.
            head.append(
                "RELEASE GATE: GO - every cloud requirement checked passed"
                if not counts["FAIL"] else
                f"RELEASE GATE: NO-GO - {counts['FAIL']} cloud requirement(s) failed"
            )
        # Failures first: they are what the OBSERVE and ADAPT steps should rank.
        order = {"FAIL": 0, "WARN": 1, "PASS": 2}
        head += [f"{status} - {text}" for status, text in sorted(self.rows, key=lambda r: order[r[0]])]
        return "\n".join(head + ["", "DETAIL:"] + [l for l in detail if l is not None])


def _get(url, timeout=10, **kwargs):
    try:
        response = requests.get(url, timeout=timeout, **kwargs)
        return response.status_code, response
    except requests.RequestException as exc:
        return None, str(exc)


def _post(url, timeout=10, **kwargs):
    try:
        response = requests.post(url, timeout=timeout, **kwargs)
        return response.status_code, response
    except requests.RequestException as exc:
        return None, str(exc)


def _rel(path):
    return str(path.relative_to(REPO_ROOT))


def _gh_latest_run(workflow_file):
    """Latest run of a workflow on main, through the GitHub CLI if present."""
    if not shutil.which("gh"):
        return "latest run: not checked (GitHub CLI not installed)"
    try:
        result = subprocess.run(
            ["gh", "run", "list", "--workflow", workflow_file, "--branch", "main",
             "--limit", "1", "--json", "conclusion,status,createdAt,url"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return f"latest run: not checked ({exc})"
    if result.returncode != 0:
        return f"latest run: not checked ({result.stderr.strip()[:120]})"
    runs = json.loads(result.stdout or "[]")
    if not runs:
        return "latest run on main: NONE"
    run = runs[0]
    return (
        f"latest run on main: {run['conclusion'] or run['status']} "
        f"({run['createdAt'][:16].replace('T', ' ')} UTC) {run['url']}"
    )


# --- Multi-Agent Workflow Review ---------------------------------------------

def _audit_problems(workflow, history):
    """Rules every workflow's audit log must satisfy. Returns the broken ones."""
    problems = []
    events = [(e["actor"], e["event"], e["detail"]) for e in history]
    names = [event for _, event, _ in events]

    if not names or names[0] != "created":
        problems.append("audit log does not start with 'created'")
    if workflow.get("plan") and "plan" not in names:
        problems.append("a plan exists but no planner 'plan' event was logged")
    if "plan" in names and "response" in names and names.index("response") < names.index("plan"):
        problems.append("the Worker responded before the Planner planned")

    reviews = names.count("review")
    if reviews != len(workflow.get("attempts", [])):
        problems.append(
            f"{len(workflow.get('attempts', []))} attempt(s) but {reviews} reviewer event(s)"
        )

    human = [d for actor, event, d in events if event == "decision" and actor.startswith("human:")]
    if workflow["status"] in FINAL_STATUSES:
        if not human:
            problems.append(f"reached '{workflow['status']}' with NO human decision")
        else:
            final = {"approved": "approve", "partially_accepted": "partial", "rejected": "reject"}
            if human[-1].get("decision") != final[workflow["status"]]:
                problems.append(
                    f"status '{workflow['status']}' does not match the last human "
                    f"decision '{human[-1].get('decision')}'"
                )
    if workflow.get("final_response") and workflow["status"] not in ("approved", "partially_accepted"):
        problems.append(f"a response was released while the workflow is '{workflow['status']}'")
    return problems


def _repo_integration(n):
    """Does student-N's backend call the Multi-Agent Server, and its page show it?"""
    api = REPO_ROOT / f"student-{n}" / "api"
    frontend = REPO_ROOT / f"student-{n}" / "frontend"
    api_hits = [
        _rel(p) for p in api.rglob("*.py")
        if "MULTI_AGENT_URL" in p.read_text(encoding="utf-8", errors="ignore")
    ] if api.exists() else []
    page_hits = [
        _rel(p) for p in frontend.rglob("*.html")
        if "/ai/agents" in p.read_text(encoding="utf-8", errors="ignore")
    ] if frontend.exists() else []
    return api_hits, page_hits


def collect_multiagent_evidence():
    lines = []
    checks = Checks()

    # --- Rules that come from the code and compose, not from a running server.
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    services = (yaml.safe_load(compose) or {}).get("services", {})
    containerised = [name for name in services if "agent" in name]
    checks.add(not containerised, "the Multi-Agent Server is NOT a docker-compose service"
               if not containerised else f"docker-compose.yml declares {containerised}")
    lines.append(
        "Containerisation rule (Multi-Agent Server must NOT be a compose service): "
        + ("OK, not in docker-compose.yml" if not containerised
           else f"VIOLATION, compose declares {containerised}")
    )

    server_src = REPO_ROOT / "ai-services" / "multi-agent-server"
    direct = [
        _rel(p) for p in server_src.glob("*.py")
        if re.search(r"11434|from openai|import openai", p.read_text(encoding="utf-8"))
    ]
    checks.add(not direct, "agents reach the model only through AI-Mode"
               if not direct else f"direct model client in {direct}")
    lines.append(
        "Model access rule (agents reach the model only through AI-Mode): "
        + ("OK, no direct Ollama/OpenAI client in ai-services/multi-agent-server"
           if not direct else f"VIOLATION in {direct}")
    )

    lines.append("\nFeature integration (backend/API calls the server; page renders the workflow):")
    integrated, missing = [], []
    for n in STUDENT_NUMBERS:
        api_hits, page_hits = _repo_integration(n)
        state = "OK" if api_hits and page_hits else "MISSING"
        (integrated if state == "OK" else missing).append(f"student-{n}")
        lines.append(
            f"  student-{n}: {state} - backend {', '.join(api_hits) or 'none'}; "
            f"page {', '.join(page_hits) or 'none'}"
        )

    if integrated:
        checks.add(True, f"integrated through backend/API and page: {', '.join(integrated)}")
    if missing:
        checks.add(False, f"NOT yet integrated with the Multi-Agent Server: {', '.join(missing)}")

    # --- The running server.
    status, response = _get(f"{MULTI_AGENT_URL}/health")
    if status != 200:
        checks.add(False, f"Multi-Agent Server unreachable at {MULTI_AGENT_URL}")
        lines.append(
            f"\nMulti-Agent Server UNREACHABLE at {MULTI_AGENT_URL} ({response}). "
            "Start it with ./scripts/ai_services.sh up"
        )
        return checks.report(lines)
    health = response.json()
    lines.append(
        f"\nMulti-Agent Server: health 200, containerised={health.get('containerised')}, "
        f"agents={health.get('agents')}, human decisions={health.get('human_review')}, "
        f"{health.get('workflows')} workflow(s) stored"
    )

    # --- Validation probes. None of these calls the model, and none changes state.
    lines.append("\nValidation probes (each must be REFUSED with the stated status):")
    probes = [
        ("unknown feature", "POST", "/workflows", {"feature": "student-9", "task": "x"}, 400),
        ("empty task", "POST", "/workflows", {"feature": "student-1", "task": ""}, 400),
        ("task over 1000 chars", "POST", "/workflows", {"feature": "student-1", "task": "x" * 1001}, 400),
        ("unknown workflow id", "GET", "/workflows/wf-does-not-exist", None, 404),
    ]
    listing = _get(f"{MULTI_AGENT_URL}/workflows", params={"limit": 50})[1].json()["workflows"]
    awaiting = next((w for w in listing if w["status"] == "awaiting_human_review"), None)
    closed = next((w for w in listing if w["status"] in FINAL_STATUSES), None)
    if awaiting:
        probes.append(("decision with no reviewer name", "POST",
                       f"/workflows/{awaiting['id']}/decision", {"decision": "approve"}, 400))
        probes.append(("reject with no notes", "POST",
                       f"/workflows/{awaiting['id']}/decision",
                       {"decision": "reject", "reviewer": "agentic-loop"}, 400))
    if closed:
        probes.append(("second decision on a closed workflow", "POST",
                       f"/workflows/{closed['id']}/decision",
                       {"decision": "approve", "reviewer": "agentic-loop"}, 409))
    leaked = []
    for label, method, path, body, expected in probes:
        call = _get if method == "GET" else _post
        kwargs = {"json": body} if body is not None else {}
        status, response = call(f"{MULTI_AGENT_URL}{path}", **kwargs)
        if status == expected:
            reason = response.json().get("error", "") if status else ""
            lines.append(f"  {label}: refused {status} - {reason[:90]}")
        else:
            leaked.append(label)
            lines.append(f"  {label}: NOT REFUSED AS EXPECTED - got {status}, wanted {expected}")
    checks.add(not leaked, f"all {len(probes)} validation probes refused with the expected status"
               if not leaked else f"probes not refused as expected: {', '.join(leaked)}")

    # --- The workflows themselves.
    if not listing:
        checks.add(False, "no workflows have been run, so there is no workflow history")
        lines.append("\nNo workflows have been run yet, so there is no workflow history to review.")
        return checks.report(lines)

    workflows, broken = [], []
    for row in listing:
        workflow = _get(f"{MULTI_AGENT_URL}/workflows/{row['id']}")[1].json()
        history = _get(f"{MULTI_AGENT_URL}/workflows/{row['id']}/history")[1].json()["history"]
        workflows.append(workflow)
        problems = _audit_problems(workflow, history)
        if problems:
            broken.append((workflow["id"], problems))

    attempts = [a for w in workflows for a in w["attempts"]]
    statuses = Counter(w["status"] for w in workflows)
    features = Counter(w["feature"] for w in workflows)
    verdicts = Counter(w["attempts"][-1]["review"]["verdict"] for w in workflows if w["attempts"])
    decisions = Counter(d["decision"] for w in workflows for d in w["decisions"])
    planner_fallbacks = sum(1 for w in workflows if (w.get("plan") or {}).get("source") == "fallback")
    reviewer_fallbacks = sum(1 for a in attempts if a["review"]["source"] == "fallback")
    deterministic = Counter(
        risk.split(":")[0].split(",")[0]
        for a in attempts for risk in a["review"]["checks"]["risks"]
    )
    missing_evidence = sum(1 for w in workflows for e in w["evidence"] if not e["ok"])
    approved_over_concerns = sum(
        1 for w in workflows for d in w["decisions"]
        if d["decision"] == "approve" and d["reviewer_verdict"] in ("concerns", "fail")
    )
    corrected = [w for w in workflows if w["round"] > 1]

    no_human = [wid for wid, problems in broken if any("NO human decision" in p for p in problems)]
    checks.add(not no_human, "no workflow reached a final status without a human decision"
               if not no_human else f"final status WITHOUT a human decision: {', '.join(no_human)}")
    checks.add(not broken, f"audit log complete and in order for all {len(workflows)} workflows"
               if not broken else f"audit log problems in {len(broken)} workflow(s)")
    checks.add(
        planner_fallbacks == 0 and reviewer_fallbacks == 0,
        "every Planner and Reviewer reply parsed (no fallbacks)" if not (planner_fallbacks or reviewer_fallbacks)
        else f"fallbacks: Planner {planner_fallbacks}/{len(workflows)}, Reviewer {reviewer_fallbacks}/{len(attempts)}",
        warn=True,
    )
    flagged = sum(1 for a in attempts if a["review"]["checks"]["risks"])
    checks.add(
        flagged == 0,
        f"{flagged} of {len(attempts)} Worker responses failed the deterministic citation checks "
        f"({dict(deterministic)})" if flagged else "every Worker response passed the citation checks",
        warn=True,
    )
    if approved_over_concerns:
        overridden = [w["id"] for w in workflows for d in w["decisions"]
                      if d["decision"] == "approve" and d["reviewer_verdict"] in ("concerns", "fail")]
        checks.add(False, f"humans approved {approved_over_concerns} response(s) the Reviewer flagged: "
                          f"{', '.join(overridden[:3])}", warn=True)
    if statuses.get("awaiting_human_review"):
        checks.add(False, f"{statuses['awaiting_human_review']} workflow(s) still awaiting human review",
                   warn=True)
    if len(features) < len(STUDENT_NUMBERS):
        checks.add(False, f"workflow history only covers {sorted(features)}", warn=True)

    lines.append(f"\nWorkflow history ({len(workflows)} most recent workflow(s)):")
    lines.append(f"  by feature: {dict(features)}")
    lines.append(f"  by status: {dict(statuses)}")
    lines.append(f"  latest Reviewer verdicts: {dict(verdicts)}")
    lines.append(f"  human decisions: {dict(decisions) or 'none yet'}")
    lines.append(
        f"  Planner fell back to the default plan in {planner_fallbacks}/{len(workflows)} "
        f"workflow(s); Reviewer reply unparseable in {reviewer_fallbacks}/{len(attempts)} review(s)"
    )
    lines.append(
        f"  deterministic citation checks raised: "
        f"{dict(deterministic) or 'nothing'}"
    )
    lines.append(f"  evidence items that could not be fetched: {missing_evidence}")
    lines.append(
        f"  approved by a human although the Reviewer reported concerns or fail: "
        f"{approved_over_concerns}"
    )
    lines.append(
        f"  corrected at least once: {len(corrected)} "
        + (f"(e.g. {corrected[0]['id']}: verdicts by round "
           f"{[a['review']['verdict'] for a in corrected[0]['attempts']]})" if corrected else "")
    )
    lines.append(
        f"  left awaiting human review: {statuses.get('awaiting_human_review', 0)}"
    )

    lines.append(
        "\nAudit log integrity (created first, plan before work, one review per attempt, "
        "every final status backed by a matching human decision): "
        + (f"OK for all {len(workflows)} workflow(s)" if not broken
           else f"VIOLATIONS in {len(broken)} workflow(s)")
    )
    for workflow_id, problems in broken[:5]:
        lines.append(f"  {workflow_id}: {'; '.join(problems)}")

    sample = next((w for w in workflows if w["status"] in FINAL_STATUSES), workflows[0])
    latest = sample["attempts"][-1] if sample["attempts"] else None
    lines.append(f"\nSample workflow {sample['id']} ({sample['feature']}, {sample['status']}):")
    lines.append(f"  task: {sample['task'][:160]}")
    if sample.get("plan"):
        lines.append(f"  plan goal: {sample['plan']['goal'][:160]}")
        lines.append(f"  acceptance criteria: {sample['plan']['acceptance_criteria']}")
    if latest:
        lines.append(f"  Worker response: {latest['worker']['response'][:300]}")
        lines.append(f"  Reviewer verdict: {latest['review']['verdict']}, risks: {latest['review']['risks'][:3]}")
    for d in sample["decisions"]:
        lines.append(f"  human: {d['decision']} by {d['reviewer']} (round {d['round']})")

    return checks.report(lines)


# --- Testing Review -------------------------------------------------------------

# Calls a test makes against an endpoint: requests.get(f"{API}/trips"),
# client.post("/days"), and so on. Calls through a variable whose name says DB
# are setup and cleanup against the database service, not the API under test.
# The closing quote must match the opening one, because an f-string such as
# f"{API}/trips/{trip['trip_id']}/days" has the other quote inside it.
ENDPOINT_CALL = re.compile(
    r"\.(get|post|put|delete|patch)\(\s*f?([\"'])(?:\{(\w+)\})?(/.*?)\2"
)


def _endpoints_in(test_file):
    found = set()
    for method, _quote, base, path in ENDPOINT_CALL.findall(test_file.read_text(encoding="utf-8")):
        if base and "DB" in base.upper():
            continue
        path = path.split("?")[0]
        # /trips/{trip_id}/days and /guides/14 are the same endpoint as any
        # other id, so ids are normalised before counting distinct endpoints.
        path = re.sub(r"\{[^}]*\}|(?<=/)\d+(?=/|$)", "<id>", path)
        found.add(f"{method.upper()} {path}")
    return found


def _ci_test_files(workflow_text, n):
    """Test files a student-x.yml actually runs with pytest."""
    files = set()
    for step in re.findall(r"pytest[^\n]*(?:\n\s{10,}[^\n]+)*", workflow_text):
        for target in re.findall(rf"student-{n}/tests[\w/.-]*", step):
            path = REPO_ROOT / target
            if path.is_dir():
                files.update(path.glob("test_*.py"))
            elif path.exists():
                files.add(path)
    return sorted(files)


def _pre_commit_evidence(checks):
    lines = []
    config_path = REPO_ROOT / ".pre-commit-config.yaml"
    if not config_path.exists():
        checks.add(False, "no .pre-commit-config.yaml: Ruff security rules, detect-secrets and "
                          "pip-audit are all missing")
        lines.append(".pre-commit-config.yaml: MISSING - no pre-commit security scans are configured")
        return lines

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    hooks = [
        (repo.get("repo", ""), hook.get("id", ""), hook.get("args", []))
        for repo in config.get("repos", []) for hook in repo.get("hooks", [])
    ]
    lines.append(f".pre-commit-config.yaml: {len(hooks)} hook(s): "
                 + ", ".join(hook_id for _, hook_id, _ in hooks))

    ruff_config = " ".join(
        (REPO_ROOT / name).read_text(encoding="utf-8")
        for name in ("ruff.toml", ".ruff.toml", "pyproject.toml") if (REPO_ROOT / name).exists()
    )
    ruff = [h for h in hooks if h[1].startswith("ruff")]
    ruff_security = any(
        re.search(r"(^|[,\s=\"'\[])S(\d*)?([,\s\"'\]]|$)", " ".join(args)) for _, _, args in ruff
    ) or bool(re.search(r"select\s*=\s*\[[^\]]*\"S\"", ruff_config))
    checks.add(bool(ruff and ruff_security), "Ruff security rules (S) run on commit"
               if ruff and ruff_security else "Ruff security rules (S) are not configured")
    lines.append("  Ruff security rules (S / flake8-bandit): "
                 + ("OK" if ruff and ruff_security else
                    "MISSING - ruff not configured" if not ruff else
                    "MISSING - ruff runs but the S rules are not selected"))

    secrets = [h for h in hooks if h[1] == "detect-secrets"]
    baseline = (REPO_ROOT / ".secrets.baseline").exists()
    checks.add(bool(secrets and baseline), "detect-secrets runs on commit with a committed baseline"
               if secrets and baseline else "detect-secrets is missing or has no .secrets.baseline")
    lines.append("  detect-secrets: "
                 + ("OK, with .secrets.baseline" if secrets and baseline else
                    "configured but NO .secrets.baseline committed" if secrets else "MISSING"))

    audit = [h for h in hooks if "audit" in h[1]]
    checks.add(bool(audit), "pip-audit (dependency audit) runs on commit" if audit
               else "no pip-audit or equivalent dependency audit")
    lines.append("  pip-audit (or equivalent): " + ("OK" if audit else "MISSING"))

    reports = sorted(
        (p for p in (REPO_ROOT / "docs" / "evidence").rglob("*")
         if p.is_file() and re.search(r"pre-?commit|security-scan", p.name, re.I)),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    checks.add(bool(reports), "a pre-commit scan report is saved in docs/evidence" if reports
               else "no pre-commit scan report saved in docs/evidence for the technical report")
    if not reports:
        lines.append("  saved scan report in docs/evidence: NONE")
    else:
        report = reports[0]
        text = report.read_text(encoding="utf-8", errors="ignore") if report.suffix != ".png" else ""
        lines.append(f"  latest saved scan report: {_rel(report)}")
        summary = [l.strip() for l in text.splitlines()
                   if re.search(r"Passed|Failed|Skipped|found|vulnerab|error", l, re.I)]
        for line in summary[:15]:
            lines.append(f"    {line[:150]}")
    return lines


def collect_testing_evidence():
    checks = Checks()
    lines = ["PRE-COMMIT SECURITY TESTING"]
    lines += _pre_commit_evidence(checks)

    lines.append("\nPOST-COMMIT CI/CD ENDPOINT TESTING (requirement: each student-x.yml tests "
                 "two endpoint functions of that student's backend/API)")
    for n in STUDENT_NUMBERS:
        workflow_file = f"student-{n}.yml"
        path = REPO_ROOT / ".github" / "workflows" / workflow_file
        if not path.exists():
            checks.add(False, f"student-{n}: {workflow_file} is missing")
            lines.append(f"\nstudent-{n}: {workflow_file} MISSING")
            continue
        text = path.read_text(encoding="utf-8")
        test_files = _ci_test_files(text, n)
        endpoints = set()
        test_count = 0
        for test_file in test_files:
            endpoints |= _endpoints_in(test_file)
            test_count += len(re.findall(r"^def test_", test_file.read_text(encoding="utf-8"), re.M))

        verdict = (
            "OK, at least two" if len(endpoints) >= 2 else
            "BELOW REQUIREMENT" if test_files else "MISSING - no pytest step"
        )
        lines.append(f"\nstudent-{n} ({workflow_file}):")
        lines.append(f"  pytest files run in CI: {', '.join(_rel(f) for f in test_files) or 'none'}")
        lines.append(f"  test functions: {test_count}")
        lines.append(
            f"  distinct API endpoints called by those tests: {len(endpoints)} -> {verdict}"
            + (f": {', '.join(sorted(endpoints)[:8])}" if endpoints else "")
        )
        lines.append(
            "  smoke test also runs: " + ("yes" if f"smoke_test.py {n}" in text else "no")
        )
        published = [label for label, present in (
            ("JUnit XML", "--junitxml" in text),
            ("job summary", "GITHUB_STEP_SUMMARY" in text),
            ("uploaded artifact", "upload-artifact" in text),
        ) if present]
        lines.append(f"  test report published: {', '.join(published) or 'none'}")
        latest = _gh_latest_run(workflow_file)
        lines.append(f"  {latest}")

        checks.add(
            len(endpoints) >= 2,
            f"student-{n}: CI tests {len(endpoints)} distinct endpoints of its backend/API"
            + ("" if len(endpoints) >= 2 else
               " (needs two; the smoke test alone does not count)" if not test_files else " (needs two)"),
        )
        if "latest run on main: success" not in latest and "not checked" not in latest:
            checks.add(False, f"student-{n}: {latest}")
        if len(endpoints) >= 2 and not published:
            checks.add(False, f"student-{n}: no test report published (JUnit, job summary or artifact)",
                       warn=True)

    lines.append(
        "\nNote: endpoint counts come from the HTTP calls written in the test files "
        "(calls made through a DB-named base URL are excluded as setup)."
    )
    return checks.report(lines)


# --- Cloud Deployment Review ----------------------------------------------------

AI_FLAGS = ("AI_MODE_ENABLED", "MCP_ENABLED", "RAG_ENABLED", "MULTI_AGENT_ENABLED")
SECRET_PATTERNS = re.compile(
    r"AKIA[0-9A-Z]{16}"                                  # AWS access key id
    r"|(?i:(?:password|secret|client_secret|access_key)\s*[:=]\s*[\"']?(?!\$\{\{)[A-Za-z0-9/+=]{12,})"
)


def _deployment_files():
    candidates = []
    for pattern in ("scripts/cloud/**/*", "infra/**/*", "deploy/**/*", "**/*.bicep",
                    "**/*.tf", "**/cloudformation*.y*ml", "scripts/*deploy*"):
        candidates += [p for p in REPO_ROOT.glob(pattern) if p.is_file()]
    return sorted({
        p for p in candidates
        if ".venv" not in p.parts and "node_modules" not in p.parts and ".git" not in p.parts
    })


def _cloud_url():
    url = os.getenv("CLOUD_APP_URL", "").strip()
    saved = REPO_ROOT / "docs" / "evidence" / "cloud-app-url.txt"
    if not url and saved.exists():
        url = saved.read_text(encoding="utf-8").strip()
    return url.rstrip("/")


def collect_cloud_evidence():
    lines = []
    checks = Checks()
    workflow_path = REPO_ROOT / ".github" / "workflows" / "cloud-deployment.yml"

    # --- The deployment workflow.
    checks.add(workflow_path.exists(), "cloud-deployment.yml exists" if workflow_path.exists()
               else "there is no .github/workflows/cloud-deployment.yml")
    if not workflow_path.exists():
        lines.append("cloud-deployment.yml: MISSING - there is no cloud deployment workflow")
    else:
        text = workflow_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text) or {}
        triggers = parsed.get(True, parsed.get("on", {}))  # PyYAML reads `on:` as True
        jobs = parsed.get("jobs", {})
        gated = (
            isinstance(triggers, dict) and "workflow_run" in triggers
            and "success" in text
        ) or any(job.get("needs") for job in jobs.values() if isinstance(job, dict))
        checks.add(gated, "deployment runs only after the student CI workflows succeed" if gated
                   else "nothing gates the deployment on CI validation passing")
        lines.append(f"cloud-deployment.yml: present, {len(text.splitlines())} lines")
        lines.append(f"  triggers: {list(triggers) if isinstance(triggers, dict) else triggers}")
        lines.append(f"  jobs: {list(jobs)}")
        lines.append(
            "  deploys only after CI validation succeeds: "
            + ("OK (workflow_run on success, or needs: on test jobs)" if gated else
               "MISSING - nothing gates the deployment on the student workflows passing")
        )
        steps = [
            step.get("name") or step.get("uses") or "unnamed"
            for job in jobs.values() if isinstance(job, dict)
            for step in job.get("steps", [])
        ]
        lines.append(f"  steps: {steps[:14]}")
        secrets = sorted(set(re.findall(r"secrets\.([A-Z0-9_]+)", text)))
        lines.append(f"  GitHub secrets referenced: {secrets or 'none'}")

    # --- Reusable deployment scripts / IaC.
    files = _deployment_files()
    checks.add(bool(files), f"{len(files)} deployment script / IaC file(s) found" if files
               else "no reusable deployment scripts or infrastructure-as-code files")
    lines.append(
        f"\nDeployment scripts / infrastructure as code: "
        + (", ".join(_rel(p) for p in files[:12]) if files else "NONE FOUND")
    )

    # --- AI services disabled by default, and no hard-coded secrets.
    scanned = files + ([workflow_path] if workflow_path.exists() else [])
    flag_values = {flag: set() for flag in AI_FLAGS}
    leaks = []
    for path in scanned:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for flag in AI_FLAGS:
            for value in re.findall(rf"{flag}\W{{1,4}}([A-Za-z0-9]+)", text):
                flag_values[flag].add(value.lower())
        for match in SECRET_PATTERNS.finditer(text):
            leaks.append(f"{_rel(path)}: {match.group(0)[:24]}...")
    lines.append("\nAI services disabled by default in the cloud configuration:")
    not_false = [flag for flag, values in flag_values.items() if values != {"false"}]
    checks.add(not not_false, "all four AI flags are set to false in the cloud configuration"
               if not not_false else f"not set to false in the cloud configuration: {', '.join(not_false)}")
    if scanned:
        checks.add(not leaks, "no hard-coded credentials in deployment files" if not leaks
                   else f"possible hard-coded credentials: {leaks[:2]}")
    for flag, values in flag_values.items():
        state = ("OK, false" if values == {"false"} else
                 "NOT SET - would default to true" if not values else
                 f"CHECK, set to {sorted(values)}")
        lines.append(f"  {flag}: {state}")
    lines.append(
        "Hard-coded credentials in deployment files: "
        + ("none found" if not leaks else f"POSSIBLE LEAK {leaks[:3]}")
    )

    if workflow_path.exists():
        latest = _gh_latest_run("cloud-deployment.yml")
        lines.append(f"\ncloud-deployment.yml {latest}")
        if "not checked" not in latest:
            checks.add("latest run on main: success" in latest, f"cloud-deployment.yml {latest}")

    # --- The deployed application.
    url = _cloud_url()
    if not url:
        checks.add(False, "no deployed application to check (CLOUD_APP_URL not set, no "
                          "docs/evidence/cloud-app-url.txt)")
        lines.append(
            "\nDeployed application: NOT CHECKED - set CLOUD_APP_URL or save the URL to "
            "docs/evidence/cloud-app-url.txt"
        )
        return checks.report(lines, release_gate=True)

    lines.append(f"\nDeployed application at {url}:")
    status, response = _get(f"{url}/", timeout=20)
    checks.add(status == 200 and "NextStop" in response.text,
               f"the deployed frontend serves the NextStop page at {url}" if status == 200
               else f"the deployed frontend did not answer 200 at {url} (got {status})")
    lines.append(
        f"  GET / : {status or 'UNREACHABLE'}"
        + (f", NextStop page {'served' if 'NextStop' in response.text else 'NOT recognised'}"
           if status == 200 else f" ({response if status is None else ''})")
    )
    down = []
    for n in STUDENT_NUMBERS:
        status, _ = _get(f"{url}/api/student-{n}/health", timeout=15)
        if status != 200:
            down.append(f"student-{n}")
        lines.append(f"  student-{n}-api health through the cloud frontend: {status or 'UNREACHABLE'}")
    checks.add(not down, "all five backend/APIs answer through the cloud frontend" if not down
               else f"backend/APIs not answering in the cloud: {', '.join(down)}")

    status, response = _get(f"{url}/api/student-1/trips", timeout=20)
    crud = status == 200 and "<table" in response.text
    checks.add(crud, "CRUD read works in the cloud (student-1 trips table)" if crud
               else f"CRUD read failed in the cloud (GET /api/student-1/trips -> {status})")
    lines.append(
        f"  CRUD read, GET /api/student-1/trips: {status or 'UNREACHABLE'}"
        + (", trips table returned" if status == 200 and "<table" in response.text else "")
    )

    lines.append("  AI paths (each must answer with the disabled notice, not a result):")
    enabled = []
    for label, path, form in (
        ("AI-Mode chat", "/api/student-1/ai/chat", {"question": "hello"}),
        ("MCP", "/api/student-1/ai/mcp", {"tool": "list_trips"}),
        ("RAG", "/api/student-1/ai/rag", {"question": "How should I split a trip budget?"}),
        ("Multi-Agent", "/api/student-1/ai/agents", {"task": "Summarise trip 1"}),
    ):
        status, response = _post(f"{url}{path}", data=form, timeout=30)
        if status is None:
            lines.append(f"    {label}: UNREACHABLE ({response})")
        elif "disabled in this environment" in response.text:
            lines.append(f"    {label}: OK, disabled ({status})")
        else:
            enabled.append(label)
            lines.append(f"    {label}: NOT DISABLED - answered {status} without the disabled notice")
    checks.add(not enabled, "AI-Mode, MCP, RAG and Multi-Agent all answer 'disabled' in the cloud"
               if not enabled else f"AI paths NOT disabled in the cloud: {', '.join(enabled)}")

    return checks.report(lines, release_gate=True)
