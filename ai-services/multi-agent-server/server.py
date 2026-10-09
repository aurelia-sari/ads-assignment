"""Shared local Multi-Agent Server for Group 25 (Release 2).

One non-containerised server on the host, used by all five student features.
Like AI-Mode, MCP and RAG it is deliberately not a docker-compose service;
containerised backends reach it over host.docker.internal.

Request flow:
    Frontend -> student-N-api -> Multi-Agent Server
                                   -> Planner   (plan + evidence choice)
                                   -> evidence  (MCP tools, RAG retrieval, supplied data)
                                   -> Worker    (response from evidence only)
                                   -> Reviewer  (model review + deterministic checks)
                                   -> Human Review
             <- response to the frontend once a human decides

Every agent reaches the model through AI-Mode, never Ollama directly.

A workflow stops at `awaiting_human_review`. Nothing an agent produced counts
as the final response until a person decides:

  approve   accept the Worker's response as it stands
  correct   send feedback; the Worker and Reviewer run again, and the
            workflow comes back for another human decision
  partial   accept with reservations - the notes (and an optionally edited
            response) are recorded with it
  reject    no response is released

Run it with:  ./scripts/ai_services.sh up
Terminal:     ./scripts/dev.sh agents run --feature student-1 --task "..."
"""

import os

from flask import Flask, jsonify, request
from flask_cors import CORS

import agents
import evidence
import store

app = Flask(__name__)
CORS(app)

FEATURES = ("student-1", "student-2", "student-3", "student-4", "student-5")
DECISIONS = ("approve", "correct", "partial", "reject")
FINAL_STATUS = {"approve": "approved", "partial": "partially_accepted", "reject": "rejected"}

MAX_TASK_CHARS = 1000
# Each correction is another two model calls. Three rounds is enough to fix a
# response; past that the human should edit it (partial) or reject it.
MAX_ROUNDS = int(os.getenv("MULTI_AGENT_MAX_ROUNDS", "3"))


def _error(message, status=400, **extra):
    return jsonify({"error": message, **extra}), status


def _transition(workflow, status, actor, detail=None):
    previous = workflow.get("status")
    workflow["status"] = status
    store.audit(workflow["id"], actor, "status", {"from": previous, "to": status, **(detail or {})})
    store.save(workflow)


def _run_worker_and_reviewer(workflow, feedback=None):
    """One Worker attempt and its review. Appends to workflow["attempts"]."""
    previous = workflow["attempts"][-1]["worker"]["response"] if workflow["attempts"] else None

    _transition(workflow, "working", "worker", {"round": workflow["round"]})
    worker = agents.work(workflow["task"], workflow["plan"], workflow["evidence"], feedback, previous)
    store.audit(workflow["id"], "worker", "response", {
        "round": workflow["round"],
        "applied_feedback": bool(feedback),
        "chars": len(worker["response"]),
    })

    _transition(workflow, "reviewing", "reviewer", {"round": workflow["round"]})
    review = agents.review(workflow["task"], workflow["plan"], workflow["evidence"], worker)
    store.audit(workflow["id"], "reviewer", "review", {
        "round": workflow["round"],
        "verdict": review["verdict"],
        "source": review["source"],
        "risks": len(review["risks"]),
        "cited": review["checks"]["cited"],
    })

    workflow["attempts"].append({"round": workflow["round"], "worker": worker, "review": review})
    _transition(workflow, "awaiting_human_review", "server", {"round": workflow["round"]})


def _fail(workflow, exc):
    workflow["error"] = str(exc)
    _transition(workflow, "failed", "server", {"error": str(exc)})
    return jsonify({"error": "multi-agent workflow failed", "detail": str(exc),
                    "workflow": workflow}), 503


@app.get("/health")
def health():
    return jsonify(
        {
            "service": "multi-agent-server",
            "status": "running",
            "containerised": False,
            "agents": ["planner", "worker", "reviewer"],
            "human_review": list(DECISIONS),
            "ai_mode_url": agents.AI_MODE_URL,
            "workflows": len(store.list_workflows(limit=10_000)),
        }
    )


@app.get("/agents")
def describe_agents():
    """Role descriptions, for the terminal and the report."""
    return jsonify(
        {
            "planner": "Creates the plan, chooses the evidence sources and sets acceptance criteria.",
            "worker": "Carries out the plan using only the gathered evidence, citing it as [E1].",
            "reviewer": "Checks the Worker's response against the plan and evidence, "
                        "lists risks and recommendations.",
            "human": "Approves, corrects, partially accepts or rejects. Nothing is "
                     "released without this step.",
        }
    )


@app.post("/workflows")
def create_workflow():
    payload = request.get_json(silent=True) or {}
    feature = (payload.get("feature") or "").strip()
    task = (payload.get("task") or "").strip()

    if feature not in FEATURES:
        return _error(f"feature must be one of {', '.join(FEATURES)}")
    if not task:
        return _error("task is required")
    if len(task) > MAX_TASK_CHARS:
        return _error(f"task must be at most {MAX_TASK_CHARS} characters")
    if not isinstance(payload.get("evidence", []), list) or not isinstance(
        payload.get("mcp_calls", []), list
    ):
        return _error("evidence and mcp_calls must be lists")

    workflow = {
        "id": store.new_id(),
        "feature": feature,
        "task": task,
        "requested_by": str(payload.get("requested_by") or feature),
        "status": None,
        "round": 1,
        "created_at": store.now(),
        "sources": evidence.candidate_sources(
            task,
            supplied=payload.get("evidence"),
            mcp_calls=payload.get("mcp_calls"),
            use_rag=payload.get("use_rag", True) is not False,
        ),
        "plan": None,
        "evidence": [],
        "attempts": [],
        "decisions": [],
        "final_response": None,
        "error": None,
    }
    store.audit(workflow["id"], workflow["requested_by"], "created", {
        "feature": feature,
        "task": task,
        "sources": [s["id"] + " " + s["label"] for s in workflow["sources"]],
    })

    try:
        _transition(workflow, "planning", "planner")
        workflow["plan"] = agents.plan(feature, task, workflow["sources"])
        store.audit(workflow["id"], "planner", "plan", {
            "source": workflow["plan"]["source"],
            "required_evidence": workflow["plan"]["required_evidence"],
            "steps": len(workflow["plan"]["steps"]),
        })

        _transition(workflow, "gathering_evidence", "server")
        workflow["evidence"] = evidence.gather(
            workflow["sources"], set(workflow["plan"]["required_evidence"])
        )
        store.audit(workflow["id"], "server", "evidence", {
            "items": [
                {"id": e["id"], "source_id": e["source_id"], "kind": e["kind"], "ok": e["ok"]}
                for e in workflow["evidence"]
            ],
        })

        _run_worker_and_reviewer(workflow)
    except agents.AgentError as exc:
        return _fail(workflow, exc)

    return jsonify(workflow), 201


@app.get("/workflows")
def list_workflows():
    rows = store.list_workflows(
        feature=request.args.get("feature") or None,
        status=request.args.get("status") or None,
        limit=min(int(request.args.get("limit", 20)), 200),
    )
    return jsonify(
        {
            "workflows": [
                {
                    "id": w["id"],
                    "feature": w["feature"],
                    "task": w["task"],
                    "status": w["status"],
                    "round": w["round"],
                    "verdict": w["attempts"][-1]["review"]["verdict"] if w["attempts"] else None,
                    "created_at": w["created_at"],
                    "updated_at": w.get("updated_at"),
                }
                for w in rows
            ]
        }
    )


@app.get("/workflows/<workflow_id>")
def get_workflow(workflow_id):
    try:
        return jsonify(store.load(workflow_id))
    except KeyError:
        return _error(f"no workflow {workflow_id}", 404)


@app.get("/workflows/<workflow_id>/history")
def workflow_history(workflow_id):
    try:
        store.load(workflow_id)
    except KeyError:
        return _error(f"no workflow {workflow_id}", 404)
    return jsonify({"workflow_id": workflow_id, "history": store.history(workflow_id)})


@app.post("/workflows/<workflow_id>/decision")
def decide(workflow_id):
    try:
        workflow = store.load(workflow_id)
    except KeyError:
        return _error(f"no workflow {workflow_id}", 404)

    payload = request.get_json(silent=True) or {}
    decision = (payload.get("decision") or "").strip().lower()
    reviewer = (payload.get("reviewer") or "").strip()
    notes = (payload.get("notes") or "").strip()
    feedback = (payload.get("feedback") or "").strip()
    edited = (payload.get("final_response") or "").strip()

    if workflow["status"] != "awaiting_human_review":
        return _error(f"workflow is {workflow['status']}, not awaiting_human_review", 409)
    if decision not in DECISIONS:
        return _error(f"decision must be one of {', '.join(DECISIONS)}")
    if not reviewer:
        return _error("reviewer is required, so the decision is attributable")
    if decision == "correct" and not feedback:
        return _error("a correction needs feedback for the Worker")
    if decision in ("partial", "reject") and not notes:
        return _error(f"a {decision} decision needs notes explaining it")
    if decision == "correct" and workflow["round"] >= MAX_ROUNDS:
        return _error(
            f"already at the {MAX_ROUNDS}-round limit; approve, partially accept "
            "with an edited response, or reject",
            409,
        )

    latest = workflow["attempts"][-1]
    record = {
        "round": workflow["round"],
        "decision": decision,
        "reviewer": reviewer,
        "notes": notes,
        "feedback": feedback or None,
        "reviewer_verdict": latest["review"]["verdict"],
        "edited_response": bool(edited) if decision == "partial" else False,
        "at": store.now(),
    }
    workflow["decisions"].append(record)
    store.audit(workflow_id, f"human:{reviewer}", "decision", record)

    if decision == "correct":
        workflow["round"] += 1
        try:
            _run_worker_and_reviewer(workflow, feedback=feedback)
        except agents.AgentError as exc:
            return _fail(workflow, exc)
        return jsonify(workflow)

    if decision == "approve":
        workflow["final_response"] = latest["worker"]["response"]
    elif decision == "partial":
        workflow["final_response"] = edited or latest["worker"]["response"]

    _transition(workflow, FINAL_STATUS[decision], f"human:{reviewer}")
    return jsonify(workflow)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("MULTI_AGENT_PORT", "5600")))
