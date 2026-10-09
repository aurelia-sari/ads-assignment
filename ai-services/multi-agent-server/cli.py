"""Terminal client for the shared Multi-Agent Server.

Release 2 requires the Planner -> Worker -> Reviewer -> Human Review workflow
to run from the terminal as well as from the frontend. This is that terminal
path: it calls the same HTTP API the feature backends call, so a workflow run
here and one run from a feature page leave identical audit trails.

    ./scripts/dev.sh agents run --feature student-1 --task "Summarise trip 1"
    ./scripts/dev.sh agents run --feature student-1 --task "..." \\
        --mcp 'get_trip_itinerary={"trip_id": 1}'
    ./scripts/dev.sh agents list [--status awaiting_human_review]
    ./scripts/dev.sh agents show  <workflow-id>
    ./scripts/dev.sh agents history <workflow-id>
    ./scripts/dev.sh agents decide <workflow-id> approve --reviewer Caroline

`run` stops at the human review step and asks for a decision, unless
--no-review is given (then decide later with `decide`).
"""

import argparse
import getpass
import json
import os
import sys
import textwrap

import requests

MULTI_AGENT_URL = os.getenv("MULTI_AGENT_URL", "http://localhost:5600")
TIMEOUT = 600


def _call(method, path, **kwargs):
    try:
        response = requests.request(method, f"{MULTI_AGENT_URL}{path}", timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        sys.exit(
            f"Multi-Agent Server at {MULTI_AGENT_URL} is not responding ({exc}).\n"
            "Start it with ./scripts/ai_services.sh up"
        )
    body = response.json()
    if response.status_code >= 400:
        print(f"HTTP {response.status_code}: {body.get('error')}")
        if body.get("detail"):
            print(f"  {body['detail']}")
        if not body.get("workflow"):
            sys.exit(1)
        return body["workflow"]
    return body


def _wrap(text, indent="    "):
    return "\n".join(
        textwrap.fill(line, width=88, initial_indent=indent, subsequent_indent=indent)
        if line.strip() else ""
        for line in str(text).splitlines()
    )


def _heading(title):
    print(f"\n=== {title} " + "=" * max(0, 70 - len(title)))


def print_workflow(workflow):
    print(f"\nworkflow {workflow['id']}  feature={workflow['feature']}  "
          f"status={workflow['status']}  round={workflow['round']}")
    print(_wrap(f"task: {workflow['task']}"))

    plan = workflow.get("plan")
    if plan:
        _heading(f"PLANNER ({plan['source']})")
        print(_wrap(f"goal: {plan['goal']}"))
        for number, step in enumerate(plan["steps"], start=1):
            print(_wrap(f"{number}. {step}"))
        print("    evidence chosen: " + (", ".join(plan["required_evidence"]) or "none"))
        for criterion in plan["acceptance_criteria"]:
            print(_wrap(f"criterion: {criterion}"))

    if workflow.get("evidence"):
        _heading("EVIDENCE")
        for item in workflow["evidence"]:
            status = "ok" if item["ok"] else "NOT AVAILABLE"
            print(f"    [{item['id']}] {item['label']}  ({status})")
            print(_wrap(item["content"][:300] + ("..." if len(item["content"]) > 300 else ""),
                        indent="        "))

    for attempt in workflow.get("attempts", []):
        worker, review = attempt["worker"], attempt["review"]
        _heading(f"WORKER (round {attempt['round']})")
        if worker.get("applied_feedback"):
            print(_wrap(f"applied feedback: {worker['applied_feedback']}"))
        print(_wrap(worker["response"]))

        _heading(f"REVIEWER (round {attempt['round']}, {review['source']}) "
                 f"verdict={review['verdict'].upper()}")
        for criterion in review["criteria"]:
            mark = "met" if criterion["met"] else "NOT MET"
            print(_wrap(f"[{mark}] {criterion['criterion']} - {criterion['note']}"))
        for risk in review["risks"]:
            print(_wrap(f"risk: {risk}"))
        for recommendation in review["recommendations"]:
            print(_wrap(f"recommendation: {recommendation}"))

    for decision in workflow.get("decisions", []):
        _heading(f"HUMAN REVIEW (round {decision['round']})")
        print(f"    {decision['decision']} by {decision['reviewer']} at {decision['at']}")
        for key in ("notes", "feedback"):
            if decision.get(key):
                print(_wrap(f"{key}: {decision[key]}"))

    if workflow.get("final_response") is not None:
        _heading("RELEASED RESPONSE")
        print(_wrap(workflow["final_response"]))
    if workflow.get("error"):
        print(f"\nerror: {workflow['error']}")


def ask_for_decision(workflow, reviewer):
    while workflow["status"] == "awaiting_human_review":
        _heading("HUMAN REVIEW")
        print("    [a]pprove  [c]orrect  [p]artially accept  [r]eject  [l]ater")
        choice = input("    decision> ").strip().lower()[:1]
        decision = {"a": "approve", "c": "correct", "p": "partial", "r": "reject"}.get(choice)
        if choice == "l":
            print(f"    left awaiting review. Decide later with: agents decide {workflow['id']} ...")
            return workflow
        if not decision:
            continue

        body = {"decision": decision, "reviewer": reviewer}
        if decision == "correct":
            body["feedback"] = input("    feedback for the Worker> ").strip()
        if decision in ("partial", "reject"):
            body["notes"] = input("    notes> ").strip()
        if decision == "partial":
            edited = input("    edited response (blank keeps the Worker's)> ").strip()
            if edited:
                body["final_response"] = edited

        if decision == "correct":
            print("    re-running Worker and Reviewer...")
        workflow = _call("POST", f"/workflows/{workflow['id']}/decision", json=body)
        print_workflow(workflow)
    return workflow


def _parse_mcp(values):
    calls = []
    for value in values or []:
        tool, _, arguments = value.partition("=")
        try:
            calls.append({"tool": tool.strip(), "arguments": json.loads(arguments or "{}")})
        except ValueError:
            sys.exit(f"--mcp arguments must be JSON: {value}")
    return calls


def main():
    parser = argparse.ArgumentParser(description="Group 25 Multi-Agent Server terminal client")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run Planner -> Worker -> Reviewer, then review it")
    run.add_argument("--feature", required=True, help="student-1 .. student-5")
    run.add_argument("--task", required=True)
    run.add_argument("--mcp", action="append", metavar="TOOL=JSON",
                     help="offer an MCP tool call as evidence, e.g. list_trips={}")
    run.add_argument("--evidence", action="append", metavar="LABEL=TEXT",
                     help="offer supplied evidence")
    run.add_argument("--no-rag", action="store_true", help="do not offer RAG retrieval")
    run.add_argument("--no-review", action="store_true", help="stop before human review")
    run.add_argument("--reviewer", default=getpass.getuser())

    listing = sub.add_parser("list", help="list recent workflows")
    listing.add_argument("--feature")
    listing.add_argument("--status")

    show = sub.add_parser("show", help="show one workflow in full")
    show.add_argument("workflow_id")

    history = sub.add_parser("history", help="show the audit log for one workflow")
    history.add_argument("workflow_id")

    decide = sub.add_parser("decide", help="record a human decision")
    decide.add_argument("workflow_id")
    decide.add_argument("decision", choices=["approve", "correct", "partial", "reject"])
    decide.add_argument("--reviewer", default=getpass.getuser())
    decide.add_argument("--notes", default="")
    decide.add_argument("--feedback", default="")
    decide.add_argument("--final-response", default="")

    args = parser.parse_args()

    if args.command == "run":
        supplied = []
        for value in args.evidence or []:
            label, _, text = value.partition("=")
            supplied.append({"label": label.strip(), "content": text})
        print(f"Running Planner -> Worker -> Reviewer for {args.feature} (this calls the "
              "model three times)...")
        workflow = _call("POST", "/workflows", json={
            "feature": args.feature,
            "task": args.task,
            "evidence": supplied,
            "mcp_calls": _parse_mcp(args.mcp),
            "use_rag": not args.no_rag,
            "requested_by": f"terminal:{args.reviewer}",
        })
        print_workflow(workflow)
        if not args.no_review:
            ask_for_decision(workflow, args.reviewer)

    elif args.command == "list":
        params = {k: v for k, v in (("feature", args.feature), ("status", args.status)) if v}
        rows = _call("GET", "/workflows", params=params)["workflows"]
        for row in rows:
            print(f"{row['id']}  {row['feature']:<10} {row['status']:<22} "
                  f"r{row['round']} {row['verdict'] or '-':<9} {row['task'][:50]}")
        if not rows:
            print("no workflows yet")

    elif args.command == "show":
        print_workflow(_call("GET", f"/workflows/{args.workflow_id}"))

    elif args.command == "history":
        for entry in _call("GET", f"/workflows/{args.workflow_id}/history")["history"]:
            print(f"{entry['ts']}  {entry['actor']:<22} {entry['event']:<10} "
                  f"{json.dumps(entry['detail'])}")

    elif args.command == "decide":
        workflow = _call("POST", f"/workflows/{args.workflow_id}/decision", json={
            "decision": args.decision,
            "reviewer": args.reviewer,
            "notes": args.notes,
            "feedback": args.feedback,
            "final_response": args.final_response,
        })
        print_workflow(workflow)


if __name__ == "__main__":
    main()
