"""HTML fragments for the multi-agent workflow tab (Release 2).

Everything that came from a model or a person goes through escape() before it
reaches the page. Agent output is untrusted text like any other input.
"""

import json
from html import escape

STAGES = ("Planner", "Evidence", "Worker", "Reviewer", "Human review")

# Which stage each server status has reached. Everything before it is done.
STAGE_OF_STATUS = {
    "planning": 0,
    "gathering_evidence": 1,
    "working": 2,
    "reviewing": 3,
    "awaiting_human_review": 4,
}
FINAL_STATUSES = ("approved", "partially_accepted", "rejected")

STATUS_PILL = {
    "awaiting_human_review": ("pill-planned", "awaiting your review"),
    "approved": ("pill-booked", "approved"),
    "partially_accepted": ("pill-completed", "partially accepted"),
    "rejected": ("pill-cancelled", "rejected"),
    "failed": ("pill-cancelled", "failed"),
}
VERDICT_PILL = {"pass": "pill-booked", "concerns": "pill-completed", "fail": "pill-cancelled"}


def _pill(css, label):
    return f"<span class='pill {css}'>{escape(label)}</span>"


def _status_pill(status):
    css, label = STATUS_PILL.get(status, ("pill-planned", (status or "").replace("_", " ")))
    return _pill(css, label)


def _list(items, tag="ul", css=""):
    if not items:
        return "<p class='muted'>None.</p>"
    rows = "".join(f"<li>{escape(str(item))}</li>" for item in items)
    return f"<{tag} class='{css}'>{rows}</{tag}>"


def _stages(workflow):
    status = workflow.get("status")
    if status in FINAL_STATUSES:
        reached, all_done = len(STAGES), True
    elif status == "failed":
        # Only a model call can fail a workflow: the Planner's, or a Worker
        # or Reviewer call after it. A recorded plan means it got past planning.
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
            "cautious default plan was used: fetch every offered source.</p>"
        )
    return (
        "<section class='agent-block'>"
        "<h4>Planner</h4>"
        f"<p><strong>Goal.</strong> {escape(plan['goal'])}</p>"
        f"{_list(plan['steps'], 'ol')}"
        "<p class='agent-label'>Acceptance criteria</p>"
        f"{_list(plan['acceptance_criteria'])}"
        f"<p class='muted'>Evidence chosen: {escape(', '.join(plan['required_evidence']) or 'none')}</p>"
        f"{note}</section>"
    )


def _evidence(items):
    if not items:
        return ""
    rows = []
    for item in items:
        state = _pill("pill-booked", "fetched") if item["ok"] else _pill("pill-cancelled", "not available")
        content = item["content"]
        if len(content) > 1200:
            content = content[:1200] + "\n..."
        rows.append(
            f"<li><strong>[{escape(item['id'])}]</strong> {escape(item['label'])} {state}"
            f"<pre class='agent-evidence'>{escape(content)}</pre></li>"
        )
    return (
        "<details class='agent-block'>"
        f"<summary><h4>Evidence ({len(items)} item{'s' if len(items) != 1 else ''})</h4></summary>"
        f"<ul class='agent-evidence-list'>{''.join(rows)}</ul></details>"
    )


def _attempt(attempt):
    worker, review = attempt["worker"], attempt["review"]
    feedback = ""
    if worker.get("applied_feedback"):
        feedback = (
            "<p class='muted'>Applied your feedback: "
            f"&ldquo;{escape(worker['applied_feedback'])}&rdquo;</p>"
        )

    criteria = "".join(
        f"<li class='{'is-met' if c['met'] else 'is-unmet'}'>"
        f"{'Met' if c['met'] else 'Not met'}: {escape(c['criterion'])}"
        + (f" <span class='muted'>&mdash; {escape(c['note'])}</span>" if c.get("note") else "")
        + "</li>"
        for c in review["criteria"]
    )
    fallback = ""
    if review.get("source") == "fallback":
        fallback = "<p class='muted'>The Reviewer's reply could not be parsed.</p>"

    return (
        "<section class='agent-block'>"
        f"<h4>Worker <span class='muted'>round {attempt['round']}</span></h4>"
        f"{feedback}<div class='agent-response'>{escape(worker['response'])}</div>"
        "</section>"
        "<section class='agent-block'>"
        f"<h4>Reviewer {_pill(VERDICT_PILL.get(review['verdict'], 'pill-planned'), review['verdict'])}</h4>"
        f"{fallback}"
        + (f"<ul class='agent-criteria'>{criteria}</ul>" if criteria else "")
        + "<p class='agent-label'>Risks</p>"
        + _list(review["risks"])
        + "<p class='agent-label'>Recommendations</p>"
        + _list(review["recommendations"])
        + "</section>"
    )


def _decisions(decisions):
    if not decisions:
        return ""
    rows = []
    for d in decisions:
        text = d.get("feedback") or d.get("notes") or ""
        rows.append(
            f"<li><strong>{escape(d['decision'])}</strong> by {escape(d['reviewer'])} "
            f"<span class='muted'>(round {d['round']}, {escape(d['at'])})</span>"
            + (f"<br>{escape(text)}" if text else "")
            + "</li>"
        )
    return (
        "<section class='agent-block'><h4>Human review</h4>"
        f"<ul>{''.join(rows)}</ul></section>"
    )


def _review_form(workflow):
    wid = escape(workflow["id"])
    latest = workflow["attempts"][-1]["worker"]["response"] if workflow["attempts"] else ""
    return f"""
<form class='agent-block agent-review-form'
      hx-post='/api/student-1/ai/agents/{wid}/decision'
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
    <textarea id='edit-{wid}' name='final_response' rows='4' disabled>{escape(latest)}</textarea>
  </div>
  <div class='form-actions'>
    <button type='submit'>Submit decision</button>
    <span class='spinner'>recording, and re-running the agents if you asked for a correction...</span>
  </div>
</form>"""


def _outcome(workflow):
    status = workflow["status"]
    if status in ("approved", "partially_accepted"):
        return (
            "<section class='agent-block agent-released'><h4>Released response</h4>"
            f"<div class='agent-response'>{escape(workflow['final_response'] or '')}</div>"
            "</section>"
        )
    if status == "rejected":
        return (
            "<section class='agent-block agent-released'><h4>No response released</h4>"
            "<p class='muted'>The reviewer rejected the agents' answer.</p></section>"
        )
    if status == "failed":
        return (
            "<div class='notice notice-error'>The workflow failed: "
            f"{escape(workflow.get('error') or 'unknown error')}</div>"
        )
    return ""


def workflow_card(workflow):
    wid = escape(workflow["id"])
    attempts = workflow.get("attempts", [])
    earlier = "".join(_attempt(a) for a in attempts[:-1])
    if earlier:
        earlier = (
            "<details class='agent-block'><summary><h4>Earlier rounds</h4></summary>"
            f"{earlier}</details>"
        )
    latest = _attempt(attempts[-1]) if attempts else ""

    return (
        "<article class='agent-run'>"
        "<header class='agent-run__head'>"
        f"<div><strong>{escape(workflow['task'])}</strong>"
        f"<p class='muted'><code>{wid}</code> &middot; round {workflow['round']}</p></div>"
        f"{_status_pill(workflow['status'])}</header>"
        f"{_stages(workflow)}"
        f"{_outcome(workflow)}"
        f"{_plan(workflow.get('plan'))}"
        f"{_evidence(workflow.get('evidence', []))}"
        f"{earlier}{latest}"
        f"{_decisions(workflow.get('decisions', []))}"
        + (_review_form(workflow) if workflow["status"] == "awaiting_human_review" else "")
        + "<details class='agent-block'>"
        f"<summary hx-get='/api/student-1/ai/agents/{wid}/history' "
        f"hx-target='#history-{wid}' hx-trigger='click once'><h4>Audit log</h4></summary>"
        f"<div id='history-{wid}'><p class='muted'>loading...</p></div></details>"
        "</article>"
    )


def workflow_list(workflows):
    if not workflows:
        return "<p class='muted'>No workflows yet for Trips &amp; Itinerary.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{escape(w['task'][:70])}{'...' if len(w['task']) > 70 else ''}</td>"
        f"<td>{_status_pill(w['status'])}</td>"
        f"<td>{escape(w['verdict'] or '-')}</td>"
        f"<td>{escape((w.get('updated_at') or w['created_at'])[:16].replace('T', ' '))}</td>"
        f"<td><button class='btn-sm btn-secondary' "
        f"hx-get='/api/student-1/ai/agents/{escape(w['id'])}' "
        "hx-target='#agents-panel' hx-swap='innerHTML'>Open</button></td>"
        "</tr>"
        for w in workflows
    )
    return (
        "<table><thead><tr><th>Task</th><th>Status</th><th>Reviewer verdict</th>"
        f"<th>Updated (UTC)</th><th></th></tr></thead><tbody>{rows}</tbody></table>"
    )


def history_table(entries):
    if not entries:
        return "<p class='muted'>No audit entries.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{escape(e['ts'][11:19])}</td>"
        f"<td>{escape(e['actor'])}</td>"
        f"<td>{escape(e['event'])}</td>"
        f"<td><code>{escape(json.dumps(e['detail'])[:220])}</code></td>"
        "</tr>"
        for e in entries
    )
    return (
        "<table class='agent-history'><thead><tr><th>Time (UTC)</th><th>Actor</th>"
        f"<th>Event</th><th>Detail</th></tr></thead><tbody>{rows}</tbody></table>"
    )
