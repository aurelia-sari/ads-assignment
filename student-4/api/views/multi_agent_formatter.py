"""HTML fragments for the Multi-Agent tab (student-4, Aurelia Sari).

Every value from the server or the model goes through escape().
"""

import json
from html import escape

API = "/api/student-4/ai/multi-agent"
DECISIONS = ("approve", "correct", "partial", "reject")
IN_FLIGHT = ("planning", "gathering_evidence", "working", "reviewing")
STATUS_PILLS = {
    "approved": "pill-booked",
    "awaiting_human_review": "pill-completed",
    "partially_accepted": "pill-planned",
    "rejected": "pill-cancelled",
    "failed": "pill-cancelled",
}


def _text(value):
    if isinstance(value, dict):
        value = value.get("description") or value.get("text") or json.dumps(value, default=str)
    return escape(str(value))


def _items(values):
    return "".join(f"<li>{_text(v)}</li>" for v in values or [])


def _status_pill(status):
    return f"<span class='pill {STATUS_PILLS.get(status, 'pill-planned')}'>{escape(status)}</span>"


def notice(message, tone="error"):
    return f"<div class='notice notice-{tone}'>{escape(message)}</div>"


def error_fragment(title, detail=""):
    return notice(title) + (f"<pre>{escape(detail)}</pre>" if detail else "")


def disabled_fragment():
    return notice(
        "Multi-Agent is disabled in this environment (MULTI_AGENT_ENABLED=false). "
        "The integration is present but switched off, so nothing was called."
    )


def _decision_form(workflow_id):
    options = "".join(f"<option value='{d}'>{d}</option>" for d in DECISIONS)
    return (
        f"<form class='agent-decision' hx-post='{API}/{escape(workflow_id)}/decision' "
        "hx-target='closest .agent-card' hx-swap='outerHTML'>"
        "<strong>Human review</strong>"
        "<input name='reviewer' placeholder='Your name' required>"
        f"<select name='decision'>{options}</select>"
        "<textarea name='comment' rows='2' "
        "placeholder='Notes, or feedback for the Worker if you choose correct'></textarea>"
        "<textarea name='final_response' rows='3' placeholder='Edited response (partial only)'></textarea>"
        "<div class='form-actions'><button type='submit'>Submit decision</button>"
        "<span class='spinner'>agents working...</span></div>"
        "</form>"
    )


def workflow_card(workflow):
    wid = str(workflow.get("id", ""))
    status = str(workflow.get("status", "unknown"))
    attempts = workflow.get("attempts") or []
    latest = attempts[-1] if attempts else {}
    worker = latest.get("worker") or {}
    review = latest.get("review") or {}
    plan = workflow.get("plan") or {}

    # An in-flight workflow (cloud async mode) refreshes itself until it reaches human review.
    poll = (
        f" hx-get='{API}/{escape(wid)}' hx-trigger='load delay:5s' hx-swap='outerHTML'"
        if status in IN_FLIGHT else ""
    )
    html = [
        f"<div class='agent-card' id='{escape(wid)}'{poll}>",
        f"<p><strong>Workflow</strong> <code>{escape(wid)}</code> {_status_pill(status)} "
        f"<span class='muted'>round {escape(str(workflow.get('round', 1)))}</span></p>",
        f"<p class='muted'>Task: {escape(str(workflow.get('task', '')))}</p>",
    ]
    if workflow.get("error"):
        html.append(notice(str(workflow["error"])))
    if plan:
        html.append(f"<details><summary>Planner</summary><ol>{_items(plan.get('steps'))}</ol></details>")
    if workflow.get("evidence"):
        evidence = "".join(
            f"<li>{escape(str(e.get('id', '')))} &middot; {escape(str(e.get('kind', '')))}"
            f" &middot; {'ok' if e.get('ok') else 'failed'}</li>"
            for e in workflow["evidence"]
        )
        html.append(f"<details><summary>Evidence gathered</summary><ul>{evidence}</ul></details>")
    if worker.get("response"):
        html.append(
            "<p><strong>Worker</strong></p>"
            f"<div class='agent-response'>{escape(str(worker['response']))}</div>"
        )
    if review:
        html.append(f"<p><strong>Reviewer</strong> verdict: {escape(str(review.get('verdict', '?')))}</p>")
        if review.get("risks"):
            html.append(f"<p class='muted'>Risks</p><ul>{_items(review['risks'])}</ul>")
        if review.get("recommendations"):
            html.append(f"<p class='muted'>Recommendations</p><ul>{_items(review['recommendations'])}</ul>")

    if status == "awaiting_human_review":
        html.append(_decision_form(wid))
    else:
        for d in workflow.get("decisions") or []:
            note = d.get("notes") or d.get("feedback") or ""
            html.append(
                f"<p class='muted'>Decision: {escape(str(d.get('decision', '')))} "
                f"by {escape(str(d.get('reviewer', '')))} &middot; {escape(str(note))}</p>"
            )
        if workflow.get("final_response"):
            html.append(
                "<p><strong>Released response</strong></p>"
                f"<div class='agent-response'>{escape(str(workflow['final_response']))}</div>"
            )

    html.append(
        f"<button type='button' class='chip' hx-get='{API}/{escape(wid)}/history' "
        "hx-target='next .agent-history' hx-swap='innerHTML'>View audit trail</button>"
        "<div class='agent-history'></div></div>"
    )
    return "".join(html)


def history_table(entries):
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(e.get('ts', '')))}</td>"
        f"<td>{escape(str(e.get('actor', '')))}</td>"
        f"<td>{escape(str(e.get('event', '')))}</td>"
        f"<td><code>{escape(json.dumps(e.get('detail', {}), default=str))}</code></td>"
        "</tr>"
        for e in entries
    )
    return (
        "<div class='table-wrap'><table><thead><tr><th>When</th><th>Actor</th><th>Event</th>"
        f"<th>Detail</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


def workflow_list(workflows):
    if not workflows:
        return "<p class='muted'>No workflows yet.</p>"
    return "".join(
        "<div class='request-row'><div>"
        f"<code>{escape(str(w['id']))}</code> {_status_pill(str(w['status']))}"
        f"<div class='request-row__meta'>{escape(str(w['task']))}</div></div>"
        f"<button type='button' class='chip' hx-get='{API}/{escape(str(w['id']))}' "
        "hx-target='#agent-result' hx-swap='innerHTML'>Open</button></div>"
        for w in workflows
    )
