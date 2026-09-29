"""HTML fragment builders for the Travel Mate AI (student-3, Tanishpreet Kour).
 
Every value from the database or the model goes through escape().
"""
 
from html import escape
 
 
def _card(inner):
    return f'<div class="card">{inner}</div>'
 
 
def match_fragment(result):
    status = result["status"]
 
    if status == "no_own_post":
        return '<p class="chat-log__empty">Post a trip first so the AI has something to match against.</p>'
    if status == "no_candidates_for_destination":
        return _card(
            "<p>No one else has an open trip post to "
            f"<strong>{escape(result['hint'])}</strong> right now. "
            "Check back later, or try asking about a different destination.</p>"
        )
    if status == "no_candidates":
        return _card("<p>No other open trip posts to compare against yet.</p>")
    if status == "error":
        return _card(
            f'<p class="error">AI request failed: {escape(result["error"])}. '
            "Is Ollama running with the model pulled?</p>"
        )
 
    rows = "".join(
        '<div class="chat-msg bot"><div class="who">Travel Mate AI</div>'
        f'<div class="bubble"><strong>{escape(candidate["destination"])}</strong> '
        f'<span class="compat-score"><span class="compat-score__num">{escape(str(match.get("score", "?")))}%</span></span>'
        f'<span class="compat-reason">{escape(str(match.get("reason", "")))}</span></div></div>'
        for candidate, match in result["matches"]
    )
    notes = ""
    if result["adapted"]:
        notes += " Widened the search since no matches were found for your exact destination."
    if result["low_confidence"]:
        notes += " No strong matches found — try widening your dates or travel style."
    return rows + f'<p class="muted">{escape(notes)}</p>'