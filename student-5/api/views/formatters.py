from html import escape

CONFIDENCE_LABELS = {
    "insufficient": ("Insufficient context", "confidence-insufficient"),
    "low": ("Low confidence", "confidence-low"),
    "medium": ("Medium confidence", "confidence-medium"),
    "high": ("High confidence", "confidence-high"),
}


def notice(message, kind="ok"):
    css = "notice notice-success" if kind == "ok" else f"notice notice-{kind}"
    return f"<div class='{css}'>{escape(message)}</div>"


def error_fragment(message, detail=""):
    detail_html = f"<p class='muted' style='margin-top:0.5rem'>{escape(detail)}</p>" if detail else ""
    return f"<div class='notice notice-error'>{escape(message)}{detail_html}</div>"


def _confidence_html(confidence, confidence_reason=None):
    """Confidence badge PLUS the full reasoning sentence shown as visible
    text underneath it, not just hidden in a title tooltip."""
    if not confidence:
        return ""
    label, css = CONFIDENCE_LABELS.get(confidence, (confidence, "confidence-unknown"))
    badge = f"<span class='confidence-badge {css}'>{escape(label)}</span>"
    reason_html = ""
    if confidence_reason:
        reason_html = (
            f"<div class='confidence-reason' style='margin-top:0.35rem; "
            f"font-size:0.9rem; color:var(--muted, #666);'>{escape(confidence_reason)}</div>"
        )
    return f"<div class='confidence-block'>{badge}{reason_html}</div>"


def _excerpt_text(citation):
    """RAG servers vary in what they call the passage text field.
    Check the common names so excerpts show up regardless of which
    one the shared RAG server actually uses."""
    for key in ("excerpt", "text", "passage", "content", "chunk", "snippet"):
        value = citation.get(key)
        if value:
            return value
    return ""


def _citations_html(citations):
    if not citations:
        return ""
    items = []
    for c in citations:
        source = c.get("source") or c.get("source_file") or "knowledge base"
        section = c.get("section")
        number = c.get("number")
        excerpt = _excerpt_text(c)

        header = f"[{escape(str(number))}] " if number is not None else ""
        header += escape(source)
        if section:
            header += f" &middot; {escape(section)}"

        excerpt_html = ""
        if excerpt:
            excerpt_html = (
                f"<div class='citation-excerpt' style='margin-top:0.25rem; "
                f"font-size:0.9rem; color:var(--muted, #666); "
                f"white-space:pre-wrap;'>{escape(excerpt)}</div>"
            )

        items.append(f"<li><div>{header}</div>{excerpt_html}</li>")

    return (
        "<div class='citations' style='margin-top:0.75rem'>"
        "<div class='citations-label'>Sources (via RAG)</div>"
        f"<ul>{''.join(items)}</ul>"
        "</div>"
    )


def _mcp_html(mcp_notes):
    if not mcp_notes:
        return ""
    items = "".join(f"<li>{escape(note)}</li>" for note in mcp_notes)
    return (
        "<div class='mcp-notes' style='margin-top:0.75rem'>"
        "<div class='citations-label'>Live context used (via MCP)</div>"
        f"<ul>{items}</ul>"
        "</div>"
    )


def chat_exchange(question, answer, citations=None, confidence=None,
                   confidence_reason=None, mcp_notes=None):
    confidence_html = _confidence_html(confidence, confidence_reason)
    citations_html = _citations_html(citations)
    mcp_html = _mcp_html(mcp_notes)

    return f"""
    <div class="chat-msg user">
        <div class="who">You</div>
        <div class="bubble">{escape(question)}</div>
    </div>
    <div class="chat-msg bot">
        <div class="who">NextStop AI</div>
        <div class="bubble">
            {confidence_html}
            <p style="white-space:pre-wrap; margin:0.5rem 0 0 0;">{escape(answer)}</p>
            {citations_html}
            {mcp_html}
        </div>
    </div>
    """