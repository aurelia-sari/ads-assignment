"""HTML fragment builders for the Travel Guides AI assistant (student-4, Aurelia Sari)."""

from html import escape


def error_fragment(message, detail=""):
    body = f"<div class='notice notice-error'>{escape(message)}</div>"
    if detail:
        body += f"<pre>{escape(str(detail)[:600])}</pre>"
    return body


def _answer_html(result):
    answer = escape(result["answer"])

    redirect_path = result.get("redirect_path")
    if redirect_path:
        link = f"<a href='{escape(redirect_path)}'>{escape(redirect_path)}</a>"
        answer = answer.replace(escape(redirect_path), link)

    answer = answer.replace("\n", "<br>")
    if result.get("adapted"):
        return f"<div class='notice notice-ok' style='margin-top:0.4rem'>{answer}</div>"
    return answer


def chat_turn_fragment(session_id, question, result):
    return (
        f"<input type='hidden' id='chat-session-id' name='session_id' "
        f"value='{session_id}' hx-swap-oob='true'>"
        "<div class='chat-msg user'><div class='who'>You</div>"
        f"<div class='bubble'>{escape(question)}</div></div>"
        "<div class='chat-msg bot'><div class='who'>NextStop AI</div>"
        f"<div class='bubble'>{_answer_html(result)}</div></div>"
    )


def message_row(message):
    css = "user" if message["role"] == "user" else "bot"
    who = "You" if message["role"] == "user" else "NextStop AI"
    content = escape(message["content"]).replace("\n", "<br>")
    return (
        f"<div class='chat-msg {css}'><div class='who'>{who}</div>"
        f"<div class='bubble'>{content}</div></div>"
    )


def session_fragment(session):
    messages_html = "".join(message_row(m) for m in session["messages"]) or (
        "<p class='muted'>No messages yet. Ask a question below.</p>"
    )
    hidden_session_id = (
        f"<input type='hidden' id='chat-session-id' name='session_id' "
        f"value='{session['id']}' hx-swap-oob='true'>"
    )
    return messages_html + hidden_session_id


def session_row(session):
    label = f"{escape(session['city'])}, {escape(session['country'])}"
    return (
        f"<div id='session-row-{session['id']}' style='display:flex; align-items:center; "
        "justify-content:space-between; padding:0.5rem 0; "
        "border-bottom:1px solid var(--color-slate-200)'>"
        f"<a href='#' hx-get='/api/student-4/ai/guide-chat/session/{session['id']}' "
        "hx-target='#chat-log' hx-swap='innerHTML' style='font-weight:600'>"
        f"{label} <span class='muted'>{escape(session['created_at'])}</span></a>"
        f"<button type='button' class='btn-sm btn-danger' "
        f"hx-delete='/api/student-4/ai/guide-chat/session/{session['id']}' "
        f"hx-target='#session-row-{session['id']}' hx-swap='outerHTML' "
        "hx-confirm='Delete this chat?' "
        "hx-on::before-on-load=\"if(event.detail.xhr.status < 400) "
        "window.dispatchEvent(new CustomEvent('guide-chat-session-deleted', "
        f"{{detail: {{sessionId: '{session['id']}'}}}}))\""
        ">Delete</button>"
        "</div>"
    )


def session_list_fragment(sessions):
    if not sessions:
        return "<p class='muted'>No past chats yet.</p>"
    return "<div>" + "".join(session_row(s) for s in sessions) + "</div>"
