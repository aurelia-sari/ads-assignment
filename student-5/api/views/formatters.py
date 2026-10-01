"""Student 5 - Aung Ko Khaing
HTML fragment builders for Bookings & Budget.
"""

from html import escape

CONFIDENCE_LABELS = {
    "insufficient": ("Insufficient context", "confidence-insufficient"),
    "low": ("Low confidence", "confidence-low"),
    "medium": ("Medium confidence", "confidence-medium"),
    "high": ("High confidence", "confidence-high"),
}


def notice(message, kind="ok"):
    return f"<div class='notice notice-{kind}'>{escape(message)}</div>"


def error_fragment(message, detail=""):
    body = notice(message, "error")
    if detail:
        body += f"<pre>{escape(str(detail)[:600])}</pre>"
    return body


def _confidence_html(confidence, confidence_reason=None):
    if not confidence:
        return ""

    label, css = CONFIDENCE_LABELS.get(confidence, (confidence, "confidence-unknown"))
    title = f" title='{escape(confidence_reason)}'" if confidence_reason else ""
    return f"<span class='confidence-badge {css}'{title}>{escape(label)}</span>"


def _citations_html(citations):
    if not citations:
        return ""

    items = []
    for c in citations:
        number = c.get("number", "")
        source = c.get("source") or c.get("source_file") or "knowledge base"
        section = c.get("section") or c.get("heading") or ""
        label = f"{escape(str(source))}"
        if section:
            label += f" &middot; {escape(str(section))}"
        items.append(f"<li>[{escape(str(number))}] {label}</li>")

    return (
        "<div class='citations'>"
        "<div class='citations-label'>Sources (via RAG)</div>"
        f"<ul>{''.join(items)}</ul>"
        "</div>"
    )


def _mcp_html(mcp_notes):
    if not mcp_notes:
        return ""

    items = "".join(f"<li>{escape(str(note))}</li>" for note in mcp_notes)
    return (
        "<div class='mcp-notes'>"
        "<div class='citations-label'>Live context used (via MCP)</div>"
        f"<ul>{items}</ul>"
        "</div>"
    )


def chat_exchange(
    question,
    answer,
    citations=None,
    confidence=None,
    confidence_reason=None,
    mcp_notes=None,
):
    return (
        "<div class='chat-msg user'><div class='who'>You</div>"
        f"<div class='bubble'>{escape(question)}</div></div>"
        "<div class='chat-msg bot'><div class='who'>NextStop AI "
        f"{_confidence_html(confidence, confidence_reason)}</div>"
        f"<div class='bubble'>{escape(answer)}</div>"
        f"{_citations_html(citations)}"
        f"{_mcp_html(mcp_notes)}"
        "</div>"
    )