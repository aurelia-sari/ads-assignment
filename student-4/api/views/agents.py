"""HTML fragments for the Agents tab (student-4, Aurelia Sari).

Everything that came from a model or a person goes through escape() before it
reaches the page. The run card styles live in shared/css/theme.css.
"""

import json
from html import escape

API = "/api/student-4/ai/agents"
STAGES = ("Planner", "Evidence", "Worker", "Reviewer", "Human review")
STAGE_OF_STATUS = {
    "planning": 0,
    "gathering_evidence": 1,
    "working": 2,
    "reviewing": 3,
    "awaiting_human_review": 4,
}
IN_FLIGHT = ("planning", "gathering_evidence", "working", "reviewing")
FINAL_STATUSES = ("approved", "partially_accepted", "rejected")
STATUS_PILL = {
    "awaiting_human_review": ("pill-planned", "awaiting your review"),
    "approved": ("pill-booked", "approved"),
    "partially_accepted": ("pill-completed", "partially accepted"),
    "rejected": ("pill-cancelled", "rejected"),
    "failed": ("pill-cancelled", "failed"),
}
VERDICT_PILL = {"pass": "pill-booked", "concerns": "pill-completed", "fail": "pill-cancelled"}
EVIDENCE_PREVIEW_CHARS = 1200
TASK_PREVIEW_CHARS = 70


def _pill(css, label):
    return f"<span class='pill {css}'>{escape(label)}</span>"


def _status_pill(status):
    css, label = STATUS_PILL.get(status, ("pill-planned", (status or "").replace("_", " ")))
    return _pill(css, label)


def _list(items, tag="ul"):
    if not items:
        return "<p class='muted'>None.</p>"
    rows = "".join(f"<li>{escape(str(item))}</li>" for item in items)
    return f"<{tag}>{rows}</{tag}>"


def _clip(text, limit):
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def _stages(workflow):
    status = workflow.get("status")
    if status in FINAL_STATUSES:
        reached, all_done = len(STAGES), True
    elif status == "failed":
        # A recorded plan means the workflow got past the Planner before it failed.
        reached = STAGES.index("Worker") if workflow.get("plan") else 0
        all_done = False
    else:
        reached, all_done = STAGE_OF_STATUS.get(status, 0), False

    items = []
    for index, name in enumerate(STAGES):
        if all_done or index < reached:
            css = "is-done"
        elif index == reached:
            css = "is-failed" if status == "failed" else "is-current"
        else:
            css = ""
        items.append(f"<li class='{css}'>{escape(name)}</li>")
    return f"<ol class='agent-stages'>{''.join(items)}</ol>"


def _plan(plan):
    if not plan:
        return ""
    note = ""
    if plan.get("source") == "fallback":
        note = (
            "<p class='muted'>The Planner's reply was not a usable plan, so the "
            "cautious default plan was used. Every offered source was fetched.</p>"
        )
    return (
        "<section class='agent-block'>"
        "<h4>Planner</h4>"
        f"<p><strong>Goal.</strong> {escape(str(plan.get('goal', '')))}</p>"
        f"{_list(plan.get('steps'), 'ol')}"
        "<p class='agent-label'>Acceptance criteria</p>"
        f"{_list(plan.get('acceptance_criteria'))}"
        f"<p class='muted'>Evidence chosen: {escape(', '.join(plan.get('required_evidence') or []) or 'none')}</p>"
        f"{note}</section>"
    )


def _evidence(items):
    if not items:
        return ""
    rows = []
    for item in items:
        state = _pill("pill-booked", "fetched") if item.get("ok") else _pill("pill-cancelled", "not available")
        content = _clip(str(item.get("content", "")), EVIDENCE_PREVIEW_CHARS)
        rows.append(
            f"<li><strong>[{escape(str(item.get('id', '')))}]</strong> {escape(str(item.get('label', '')))} {state}"
            f"<pre class='agent-evidence'>{escape(content)}</pre></li>"
        )
    return (
        "<details class='agent-block'>"
        f"<summary><h4>Evidence ({len(items)} item{'s' if len(items) != 1 else ''})</h4></summary>"
        f"<ul class='agent-evidence-list'>{''.join(rows)}</ul></details>"
    )


def _attempt(attempt):
    worker = attempt.get("worker") or {}
    review = attempt.get("review") or {}
    feedback = ""
    if worker.get("applied_feedback"):
        feedback = "<p class='muted'>Applied your feedback to this round.</p>"

    criteria = "".join(
        f"<li class='{'is-met' if c.get('met') else 'is-unmet'}'>"
        f"{'Met' if c.get('met') else 'Not met'}: {escape(str(c.get('criterion', '')))}"
        + (f" <span class='muted'>&mdash; {escape(str(c['note']))}</span>" if c.get("note") else "")
        + "</li>"
        for c in review.get("criteria") or []
    )
    fallback = ""
    if review.get("source") == "fallback":
        fallback = "<p class='muted'>The Reviewer's reply could not be parsed.</p>"

    verdict = str(review.get("verdict", "unknown"))
    return (
        "<section class='agent-block'>"
        f"<h4>Worker <span class='muted'>round {escape(str(attempt.get('round', 1)))}</span></h4>"
        f"{feedback}<div class='agent-response'>{escape(str(worker.get('response', '')))}</div>"
        "</section>"
        "<section class='agent-block'>"
        f"<h4>Reviewer {_pill(VERDICT_PILL.get(verdict, 'pill-planned'), verdict)}</h4>"
        f"{fallback}"
        + (f"<ul class='agent-criteria'>{criteria}</ul>" if criteria else "")
        + "<p class='agent-label'>Risks</p>"
        + _list(review.get("risks"))
        + "<p class='agent-label'>Recommendations</p>"
        + _list(review.get("recommendations"))
        + "</section>"
    )


def _decisions(decisions):
    if not decisions:
        return ""
    rows = []
    for d in decisions:
        text = d.get("feedback") or d.get("notes") or ""
        rows.append(
            f"<li><strong>{escape(str(d.get('decision', '')))}</strong> by {escape(str(d.get('reviewer', '')))} "
            f"<span class='muted'>(round {escape(str(d.get('round', '')))}, {escape(str(d.get('at', '')))})</span>"
            + (f"<br>{escape(str(text))}" if text else "")
            + "</li>"
        )
    return f"<section class='agent-block'><h4>Human review</h4><ul>{''.join(rows)}</ul></section>"


def _review_form(workflow):
    wid = escape(str(workflow["id"]))
    attempts = workflow.get("attempts") or []
    latest = (attempts[-1].get("worker") or {}).get("response", "") if attempts else ""
    return f"""
<form class='agent-block agent-review-form'
      hx-post='{API}/{wid}/decision'
      hx-target='#agents-panel' hx-swap='innerHTML'>
  <h4>Your decision</h4>
  <p class='muted'>Nothing is released until you decide. A correction sends your
  feedback to the Worker and the Reviewer checks the new answer.</p>
  <fieldset class='agent-decisions'>
    <legend class='sr-only-label'>Decision</legend>
    <label><input type='radio' name='decision' value='approve' checked> Approve</label>
    <label><input type='radio' name='decision' value='correct'> Correct (re-run Worker)</label>
    <label><input type='radio' name='decision' value='partial'> Partially accept</label>
    <label><input type='radio' name='decision' value='reject'> Reject</label>
  </fieldset>
  <div class='form-grid'>
    <div>
      <label for='reviewer-{wid}'>Your name</label>
      <input id='reviewer-{wid}' class='reviewer-name' type='text' name='reviewer' required autocomplete='name'>
    </div>
  </div>
  <label for='comment-{wid}'>Feedback or notes
    <span class='optional'>needed to correct, partially accept or reject</span></label>
  <textarea id='comment-{wid}' name='comment' rows='2'></textarea>
  <div class='agent-edit' hidden>
    <label for='edit-{wid}'>Edited response <span class='optional'>optional</span></label>
    <textarea id='edit-{wid}' name='final_response' rows='4' disabled>{escape(str(latest))}</textarea>
  </div>
  <div class='form-actions'>
    <button type='submit'>Submit decision</button>
    <span class='spinner'>recording, and re-running the agents if you asked for a correction...</span>
  </div>
</form>"""


def _outcome(workflow):
    status = workflow.get("status")
    if status in ("approved", "partially_accepted"):
        return (
            "<section class='agent-block agent-released'><h4>Released response</h4>"
            f"<div class='agent-response'>{escape(str(workflow.get('final_response') or ''))}</div>"
            "</section>"
        )
    if status == "rejected":
        return (
            "<section class='agent-block agent-released'><h4>No response released</h4>"
            "<p class='muted'>The reviewer rejected the agents' answer.</p></section>"
        )
    if status == "failed":
        return (
            "<div class='notice notice-error'>The workflow failed. "
            f"{escape(str(workflow.get('error') or 'Unknown error'))}</div>"
        )
    return ""


def workflow_card(workflow):
    wid = escape(str(workflow["id"]))
    status = workflow.get("status")
    attempts = workflow.get("attempts") or []
    earlier = "".join(_attempt(a) for a in attempts[:-1])
    if earlier:
        earlier = f"<details class='agent-block'><summary><h4>Earlier rounds</h4></summary>{earlier}</details>"
    latest = _attempt(attempts[-1]) if attempts else ""

    # An in-flight workflow (the cloud's async mode) refreshes itself until it reaches human review.
    poll = (
        f" hx-get='{API}/{wid}' hx-trigger='load delay:5s' hx-swap='outerHTML'"
        if status in IN_FLIGHT else ""
    )
    return (
        f"<article class='agent-run'{poll}>"
        "<header class='agent-run__head'>"
        f"<div><strong>{escape(str(workflow.get('task', '')))}</strong>"
        f"<p class='muted'><code>{wid}</code> &middot; round {escape(str(workflow.get('round', 1)))}</p></div>"
        f"{_status_pill(status)}</header>"
        f"{_stages(workflow)}"
        f"{_outcome(workflow)}"
        f"{_plan(workflow.get('plan'))}"
        f"{_evidence(workflow.get('evidence') or [])}"
        f"{earlier}{latest}"
        f"{_decisions(workflow.get('decisions') or [])}"
        + (_review_form(workflow) if status == "awaiting_human_review" else "")
        + "<details class='agent-block'>"
        f"<summary hx-get='{API}/{wid}/history' "
        f"hx-target='#history-{wid}' hx-trigger='click once'><h4>Audit log</h4></summary>"
        f"<div id='history-{wid}'><p class='muted'>loading...</p></div></details>"
        "</article>"
    )


def _workflow_row(workflow):
    wid = escape(str(workflow["id"]))
    task = str(workflow.get("task", ""))
    stamp = str(workflow.get("updated_at") or workflow.get("created_at") or "")[:16].replace("T", " ")
    return (
        f"<div class='agent-row' role='button' tabindex='0' "
        f"hx-get='{API}/{wid}' hx-target='#agents-panel' hx-swap='innerHTML' "
        "hx-trigger=\"click, keyup[key=='Enter']\">"
        f"<span class='agent-row__text'><span class='agent-row__task'>{escape(_clip(task, TASK_PREVIEW_CHARS))}</span> "
        f"<span class='muted agent-row__time'>{escape(stamp)}</span></span>"
        f"{_status_pill(workflow.get('status'))}"
        "</div>"
    )


def workflow_list(workflows):
    if not workflows:
        return "<p class='muted'>No workflows yet.</p>"
    return "<div>" + "".join(_workflow_row(w) for w in workflows) + "</div>"


def history_table(entries):
    if not entries:
        return "<p class='muted'>No audit entries.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(e.get('ts', ''))[11:19])}</td>"
        f"<td>{escape(str(e.get('actor', '')))}</td>"
        f"<td>{escape(str(e.get('event', '')))}</td>"
        f"<td><code>{escape(_clip(json.dumps(e.get('detail', {}), default=str), 400))}</code></td>"
        "</tr>"
        for e in entries
    )
    return (
        "<div class='table-wrap agent-history-wrap'><table class='agent-history'>"
        "<thead><tr><th>Time (UTC)</th><th>Actor</th><th>Event</th><th>Detail</th></tr>"
        f"</thead><tbody>{rows}</tbody></table></div>"
    )
