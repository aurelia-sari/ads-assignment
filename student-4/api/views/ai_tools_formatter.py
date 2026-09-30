"""HTML fragments for the MCP Tools and Knowledge Base tabs (student-4, Aurelia Sari)."""

import json
from html import escape

CONFIDENCE_PILLS = {
    "high": "pill-booked",
    "medium": "pill-completed",
    "low": "pill-cancelled",
}

# Checked by the MCP server before it reads anything, so a refusal here means no data was touched.
PRE_READ_BOUNDARIES = {"registered", "read-only", "allowlisted", "schema-checked"}


def notice(message, tone="error"):
    return f"<div class='notice notice-{tone}'>{escape(message)}</div>"


def disabled_fragment(service, flag):
    return notice(
        f"{service} is disabled in this environment ({flag}=false). "
        "The integration is present but switched off, so nothing was called."
    )


def unavailable_fragment(service, hint=""):
    message = f"The shared {service} server could not be reached. Start it with ./scripts/ai_services.sh up"
    return notice(message) + (f"<p class='muted'>{escape(hint)}</p>" if hint else "")


def _raw(result):
    return (
        "<details class='raw-result'><summary>Structured result (JSON)</summary>"
        f"<pre>{escape(json.dumps(result, indent=2))}</pre></details>"
    )


def _guide_link(row):
    # Opens the full guide in the Guides tab, which is where the detail view lives.
    return (
        f"<a href='#' hx-get='/api/student-4/guides/{int(row['id'])}' "
        "hx-target='#guides-results' hx-swap='innerHTML' "
        "hx-on::after-request=\"activate('guides')\" "
        "style='color:var(--accent); font-weight:600'>Open guide</a>"
    )


def mcp_result_fragment(tool_name, result):
    if result.get("isError"):
        boundary = result.get("boundary", "unknown")
        consequence = (
            "Nothing was read from the database."
            if boundary in PRE_READ_BOUNDARIES
            else "The tool ran, but its upstream service returned an error."
        )
        message = (result.get("content") or [{}])[0].get("text", "")
        return (
            "<div class='notice notice-error'>"
            f"MCP refused this call at the <strong>{escape(boundary)}</strong> boundary. {consequence}"
            "</div>"
            f"<pre>{escape(message)}</pre>" + _raw(result)
        )

    structured = result.get("structuredContent", {})
    rows = structured.get("rows", [])
    shown_args = ", ".join(f"{k}={v}" for k, v in (structured.get("arguments") or {}).items())

    header = (
        "<div class='notice notice-ok'>"
        f"Tool <strong>{escape(tool_name)}</strong> returned {structured.get('row_count', 0)} row(s) "
        f"from <strong>{escape(str(structured.get('source', '')))}</strong>"
        + (" (truncated to the tool's row limit)" if structured.get("truncated") else "")
        + f"<span class='notice__meta'>called with {escape(shown_args or 'no arguments')}</span>"
        "</div>"
    )

    if not rows:
        return header + "<p class='muted'>The tool ran and matched no destinations.</p>" + _raw(result)

    body = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('id', '')))}</td>"
        f"<td>{escape(str(row.get('city', '')))}</td>"
        f"<td>{escape(str(row.get('region', '') or ''))}</td>"
        f"<td>{escape(str(row.get('country', '')))}</td>"
        f"<td>{_guide_link(row) if 'id' in row else ''}</td>"
        "</tr>"
        for row in rows
    )
    table = (
        "<div class='table-wrap'><table>"
        "<thead><tr><th>ID</th><th>City</th><th>Region</th><th>Country</th><th>Guide</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )
    return header + table + _raw(result)


def rag_answer_fragment(question, result):
    question_html = (
        "<div class='chat-msg user'><div class='who'>You</div>"
        f"<div class='bubble'>{escape(question)}</div></div>"
    )

    # The insufficient-context reply has no sources and no confidence pill, so it cannot be mistaken for an answer.
    if not result.get("grounded"):
        return question_html + (
            "<div class='chat-msg bot'><div class='who'>NextStop AI (grounded)</div><div class='bubble'>"
            f"{escape(result.get('answer', ''))}"
            "<div class='citations'><span class='pill pill-cancelled'>insufficient context</span>"
            f"<p class='muted'>{escape(result.get('confidence_reason', ''))}</p></div>"
            "</div></div>"
        )

    confidence = result.get("confidence", "unknown")
    pill = CONFIDENCE_PILLS.get(confidence, "pill-planned")
    citations = "".join(
        f"<li>[{c['number']}] <code>{escape(c['source'])}</code> &rsaquo; {escape(c['section'])} "
        f"<span class='muted'>(score {c['score']})</span></li>"
        for c in result.get("citations", [])
    )
    answer = escape(result.get("answer", "")).replace("\n", "<br>")

    return question_html + (
        "<div class='chat-msg bot'><div class='who'>NextStop AI (grounded)</div><div class='bubble'>"
        f"{answer}"
        "<div class='citations'>"
        f"<span class='pill {pill}'>confidence: {escape(confidence)}</span>"
        f"<p class='muted'>{escape(result.get('confidence_reason', ''))}</p>"
        f"<strong>Sources</strong><ol class='citation-list'>{citations}</ol>"
        "</div></div></div>"
    )


def status_fragment(status):
    def pill(name, state):
        tone = {"available": "pill-booked", "disabled": "pill-completed"}.get(state, "pill-cancelled")
        return f"<span class='pill {tone}'>{escape(name)} {escape(state)}</span>"

    return (
        "<div class='suggestions'><span class='suggestions__label'>Status</span>"
        + pill("MCP", status["mcp"])
        + pill("RAG", status["rag"])
        + "</div>"
    )
