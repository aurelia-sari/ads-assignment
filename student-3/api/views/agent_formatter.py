"""HTML fragments for the Multi-Agent tab (student-3, Travel Mate).

Every value from the server or the model goes through escape().
"""

import json
from html import escape

API = "/api/student-3/ai/multi-agent"
DECISIONS = ("approve", "correct", "partial", "reject")


def _text(value):
    if isinstance(value, dict):
        value = (value.get("description") or value.get("text")
                 or value.get("step") or json.dumps(value, default=str))
    return escape(str(value))


def _items(values):
    return "".join(f"<li>{_text(v)}</li>" for v in values or [])


def error_fragment(title, detail=""):
    extra = (f'<pre class="muted" style="white-space:pre-wrap">{escape(detail)}</pre>'
             if detail else "")
    return f'<div class="card"><p class="error"><strong>{escape(title)}</strong></p>{extra}</div>'


def disabled_fragment():
    return ('<div class="card"><p class="muted">The Multi-Agent Server is switched off in this '
            "environment (MULTI_AGENT_ENABLED=false). It runs as a local service only.</p></div>")


def _decision_form(workflow_id):
    options = "".join(f'<option value="{d}">{d}</option>' for d in DECISIONS)
    return (
        f'<form hx-post="{API}/{escape(workflow_id)}/decision" '
        'hx-target="closest .agent-card" hx-swap="outerHTML" '
        'style="margin-top:0.75rem; display:grid; gap:0.5rem">'
        "<strong>Human review</strong>"
        '<input name="reviewer" placeholder="Your name" required>'
        f'<select name="decision">{options}</select>'
        '<textarea name="comment" rows="2" '
        'placeholder="Notes (or feedback for the Worker if you choose correct)"></textarea>'
        '<textarea name="final_response" rows="3" '
        'placeholder="Edited response (only used for partial)"></textarea>'
        '<button type="submit" class="btn-sm">Submit decision</button>'
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

    html = [
        f'<div class="card agent-card" id="{escape(wid)}">',
        f"<p><strong>Workflow</strong> <code>{escape(wid)}</code> "
        f'<span class="pill pill-{escape(status)}">{escape(status)}</span> '
        f'<span class="muted">round {escape(str(workflow.get("round", 1)))}</span></p>',
        f'<p class="muted">Task: {escape(str(workflow.get("task", "")))}</p>',
    ]
    if plan:
        html.append(f"<details><summary>Planner</summary><ol>{_items(plan.get('steps'))}</ol></details>")
    if workflow.get("evidence"):
        ev = "".join(
            f"<li>{escape(str(e.get('id', '')))} &middot; {escape(str(e.get('kind', '')))}"
            f" &middot; {'ok' if e.get('ok') else 'failed'}</li>"
            for e in workflow["evidence"]
        )
        html.append(f"<details><summary>Evidence gathered</summary><ul>{ev}</ul></details>")
    if worker.get("response"):
        html.append('<p><strong>Worker</strong></p><div style="white-space:pre-wrap">'
                    f'{escape(str(worker["response"]))}</div>')
    if review:
        html.append(f'<p><strong>Reviewer</strong> verdict: {escape(str(review.get("verdict", "?")))}</p>')
        if review.get("risks"):
            html.append(f"<p class=\"muted\">Risks</p><ul>{_items(review['risks'])}</ul>")
        if review.get("recommendations"):
            html.append(f"<p class=\"muted\">Recommendations</p><ul>{_items(review['recommendations'])}</ul>")

    if status == "awaiting_human_review":
        html.append(_decision_form(wid))
    else:
        for d in workflow.get("decisions") or []:
            html.append(f'<p class="muted">Decision: {escape(str(d.get("decision", "")))} '
                        f'by {escape(str(d.get("reviewer", "")))} '
                        f'&middot; {escape(str(d.get("notes", "")))}</p>')
        if workflow.get("final_response"):
            html.append('<p><strong>Released response</strong></p><div style="white-space:pre-wrap">'
                        f'{escape(str(workflow["final_response"]))}</div>')

    html.append(
        f'<button class="btn-sm" hx-get="{API}/{escape(wid)}/history" '
        'hx-target="next .agent-history" hx-swap="innerHTML">View audit trail</button>'
        '<div class="agent-history"></div></div>'
    )
    return "".join(html)


def history_table(entries):
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(e.get('created_at') or e.get('at') or e.get('timestamp') or ''))}</td>"
        f"<td>{escape(str(e.get('actor', '')))}</td>"
        f"<td>{escape(str(e.get('action', '')))}</td>"
        f"<td><code>{escape(json.dumps(e.get('detail', {}), default=str))}</code></td>"
        "</tr>"
        for e in entries
    )
    return ('<table class="muted"><tr><th>When</th><th>Actor</th><th>Action</th><th>Detail</th></tr>'
            f"{rows}</table>")


def workflow_list(workflows):
    if not workflows:
        return '<p class="muted">No workflows yet.</p>'
    rows = "".join(
        '<div class="request-row"><div>'
        f'<code>{escape(str(w["id"]))}</code> '
        f'<span class="pill pill-{escape(str(w["status"]))}">{escape(str(w["status"]))}</span>'
        f'<div class="request-row__meta">{escape(str(w["task"]))}</div></div>'
        f'<button class="btn-sm" hx-get="{API}/{escape(str(w["id"]))}" '
        'hx-target="#agent-result" hx-swap="innerHTML">Open</button></div>'
        for w in workflows
    )
    return rows