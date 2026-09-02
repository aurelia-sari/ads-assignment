"""HTML fragment builders returned to the frontend.

Everything user-supplied goes through escape() before it reaches the page.
"""

from html import escape


def notice(message, kind="ok"):
    return f"<div class='notice notice-{kind}'>{escape(message)}</div>"


def error_fragment(message, detail=""):
    body = notice(message, "error")
    if detail:
        body += f"<pre>{escape(str(detail)[:600])}</pre>"
    return body


def chat_exchange(question, answer):
    return (
        "<div class='chat-msg user'><div class='who'>You</div>"
        f"<div class='bubble'>{escape(question)}</div></div>"
        "<div class='chat-msg bot'><div class='who'>NextStop AI</div>"
        f"<div class='bubble'>{escape(answer)}</div></div>"
    )