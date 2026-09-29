"""Travel Mate backend/API microservice (student-3, Tanishpreet Kour).
Sits between the frontend (index.html) and the database microservice
(student-3/db/app.py, default http://localhost:5203). Never touches
student3.db directly -- all data access goes through the db service's
REST API, per the "each database container owns its schema" rule in the
project spec.
Also serves the frontend's index.html at "/" so you can test the whole
feature from one URL locally: http://localhost:5103/
"""



import json
import os
import itertools
import requests
from flask import Flask, jsonify, render_template_string, request, send_from_directory

from agentic_loop.core.orchestrator import run as run_match_turn, score_candidates, LLM_ERRORS
from views.ai_formatter import match_fragment
app = Flask(__name__)
DB_SERVICE_URL = os.environ.get("DB_SERVICE_URL", "http://localhost:5203")
FRONTEND_DIR = os.environ.get("FRONTEND_DIR", "../frontend/templates") 
# The "logged-in" traveller for this local/dev build. Swap for real auth
# (Feature 5, student-5) once that's integrated.
CURRENT_TRAVELLER_ID = int(os.environ.get("CURRENT_TRAVELLER_ID", "1"))
#newly addedddd
SHARED_API_URL = os.environ.get("SHARED_API_URL", "http://localhost:5000")
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:5400")
RAG_SERVER_URL = os.environ.get("RAG_SERVER_URL", "http://localhost:5500")
MCP_ENABLED = os.environ.get("MCP_ENABLED", "true").lower() == "true"
RAG_ENABLED = os.environ.get("RAG_ENABLED", "true").lower() == "true"





def get_traveller(traveller_id):
    """Best-effort lookup of a traveller's display name from shared-api.
    Returns None on any failure so a down shared-api never breaks Inbox."""
    try:
        r = requests.get(f"{SHARED_API_URL}/travellers/{traveller_id}", timeout=3)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def build_thread(post_id, other_id):
    r = requests.get(f"{DB_SERVICE_URL}/connect_requests", timeout=5)
    r.raise_for_status()
    all_reqs = r.json()

    thread = [
        req for req in all_reqs
        if req["to_post_id"] == post_id
        and req["from_traveller_id"] in (CURRENT_TRAVELLER_ID, other_id)
    ]
    thread.sort(key=lambda r: r["created_at"])

    for msg in thread:
        msg["is_mine"] = msg["from_traveller_id"] == CURRENT_TRAVELLER_ID
        if not msg["is_mine"]:
            traveller = get_traveller(msg["from_traveller_id"])
            msg["other_party_name"] = traveller["full_name"] if traveller else None

    return render_template_string(
        CHAT_THREAD_TMPL, messages=thread, post_id=post_id, other_id=other_id
    )


@app.get("/connect/thread/<int:post_id>/<int:other_id>")
def connect_thread(post_id, other_id):
    return build_thread(post_id, other_id)
#OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
#OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


#mcp adding
_mcp_id_counter = itertools.count(1)

def call_mcp_tool(tool_name, arguments):
    """Call one registered MCP tool and return its structured result.
    Raises requests.RequestException on transport failure, and returns
    a dict with isError=True if the MCP server refused the call (a
    boundary violation, not a network problem)."""
    payload = {
        "jsonrpc": "2.0",
        "id": next(_mcp_id_counter),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    r = requests.post(f"{MCP_SERVER_URL}/mcp", json=payload, timeout=10)
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise ValueError(body["error"].get("message", "MCP server error"))
    return body["result"]

#RAG
def call_rag_ask(question, live_context=None):
    """Call the shared RAG server's /ask endpoint and return its full
    response: answer, grounded flag, confidence, confidence_reason,
    and citations. Raises requests.RequestException on transport failure."""
    payload = {"question": question}
    if live_context:
        payload["context"] = live_context
    r = requests.post(f"{RAG_SERVER_URL}/ask", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

#AI_MODE_URL = os.environ.get("AI_MODE_URL", "http://ai-mode:5300")
# --- Serve the frontend (handy for local testing) --------------------------
@app.get("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")
SHARED_DIR = os.environ.get("SHARED_DIR", "../../shared")
@app.get("/shared/<path:filename>")
def serve_shared(filename):
    return send_from_directory(SHARED_DIR, filename)
@app.get("/health")
def health():
    try:
        r = requests.get(f"{DB_SERVICE_URL}/health", timeout=3)
        return jsonify({"service": "student-3-api", "status": "running", "db_service": r.json()})
    except requests.RequestException as exc:
        return jsonify({"service": "student-3-api", "status": "db_unreachable", "error": str(exc)}), 502
# --- HTML fragment templates ------------------------------------------------
TRIP_CARD_TMPL = """
{% for post in posts %}
<div class="card{% if post.traveller_id == current_id %} own-post{% endif %}">
    <div class="trip-card__header">
    <div>
        <span class="trip-card__destination">{{ post.destination }}</span>
        <div class="trip-card__dates">{{ post.start_date }} &rarr; {{ post.end_date }}</div>
    </div>
    <span class="pill pill-planned">{{ post.travel_style }}</span>
    </div>
        {% if post.note %}<p class="trip-card__note">{{ post.note }}</p>{% endif %}
    {% set s = (scores|default({})).get(post.post_id) %}
    <div class="trip-card__footer">
    {% if s %}<span class="compat-score"><span class="compat-score__num">{{ s.score }}%</span></span>{% endif %}
    {% if post.traveller_id == current_id %}
        <div style="display:flex; gap:0.5rem">
        <button class="btn-sm" hx-get="/api/student-3/trips/{{ post.post_id }}/edit"
                hx-target="closest .card" hx-swap="outerHTML">
            Edit
        </button>
        <button class="btn-sm" hx-delete="/api/student-3/trips/{{ post.post_id }}"
                hx-target="closest .card" hx-swap="outerHTML"
                hx-confirm="Delete this trip post?">
            Delete
        </button>
        </div>
            {% else %}
        <button class="say-hi-btn" hx-post="/api/student-3/connect"
                hx-vals='{"to_post_id": {{ post.post_id }}, "other_id": {{ post.traveller_id }}}'
                hx-target="next .thread-placeholder" hx-swap="innerHTML">
        Say Hi
        </button>
    {% endif %}
    </div>
    {% if s and s.reason %}<span class="compat-reason">{{ s.reason }}</span>{% endif %}
    <div class="thread-placeholder"></div>
</div>
{% else %}
<p class="muted">No trips match those filters yet.</p>
{% endfor %}
"""
EDIT_FORM_TMPL = """
<div class="card own-post">
    <form hx-put="/api/student-3/trips/{{ post.post_id }}"
        hx-target="closest .card" hx-swap="outerHTML">
    <div class="form-grid">
        <div>
        <label>Destination</label>
        <input name="destination" required value="{{ post.destination }}">
        </div>
        <div>
        <label>Start date</label>
        <input type="date" name="start_date" required value="{{ post.start_date }}">
        </div>
        <div>
        <label>End date</label>
        <input type="date" name="end_date" required value="{{ post.end_date }}">
        </div>
        <div>
        <label>Travel style</label>
        <input name="travel_style" required value="{{ post.travel_style }}">
        </div>
        <div style="grid-column:1/-1">
        <label>Short bio / notes</label>
        <textarea name="note" rows="3">{{ post.note }}</textarea>
        </div>
    </div>
    <div style="display:flex; gap:0.5rem; margin-top:0.75rem">
        <button type="submit">Save</button>
        <button type="button" class="btn-sm"
                hx-get="/api/student-3/trips/{{ post.post_id }}/view"
                hx-target="closest .card" hx-swap="outerHTML">
        Cancel
        </button>
    </div>
    </form>
</div>
"""
#some more experienting.....>_<
REQUEST_ROW_TMPL = """
{% for r in requests %}
<div class="request-row">
    <div>
    <span class="muted">{{ "From" if direction == "incoming" else "To" }}:</span>
    <strong>{{ r.other_party_name or "Unknown traveller" }}</strong>
    {% if r.destination %}<span class="muted"> &middot; {{ r.destination }}</span>{% endif %}
    <div class="request-row__meta">{{ r.message }} &middot; {{ r.created_at }}</div>


    {% if r.status == "accepted" %}
        <form hx-post="/api/student-3/connect" hx-target="closest .request-row" hx-swap="outerHTML"
            style="margin-top:0.5rem; display:flex; gap:0.5rem">
        <input type="hidden" name="to_post_id" value="{{ r.to_post_id }}">
        {% if direction == "incoming" %}
        <input type="hidden" name="other_id" value="{{ r.from_traveller_id }}">
        {% endif %}
        <input name="message" placeholder="Send a reply..." required style="flex:1">
        <button type="submit" class="btn-sm">Reply</button>
        </form>
    {% endif %}
    </div>


    <div class="request-row__actions">
    <span class="pill pill-{{ r.status }}">{{ r.status }}</span>
    {% if direction == "incoming" and r.status == "pending" %}
        <button class="btn-sm" hx-put="/api/student-3/connect/{{ r.request_id }}"
                hx-vals='{"status": "accepted"}' hx-target="closest .request-row" hx-swap="outerHTML">Accept</button>
        <button class="btn-sm" hx-put="/api/student-3/connect/{{ r.request_id }}"
                hx-vals='{"status": "declined"}' hx-target="closest .request-row" hx-swap="outerHTML">Decline</button>
    {% elif direction == "outgoing" and r.status == "pending" %}
        <button class="btn-sm" hx-delete="/api/student-3/connect/{{ r.request_id }}"
                hx-target="closest .request-row" hx-swap="outerHTML">Withdraw</button>
    {% else %}
        <button class="btn-sm btn-danger" hx-delete="/api/student-3/connect/{{ r.request_id }}"
                hx-target="closest .request-row" hx-swap="outerHTML"
                hx-confirm="Remove this request from your history?">Remove</button>
    {% endif %}
    </div>
</div>
{% else %}
<p class="muted">Nothing here yet.</p>
{% endfor %}
"""
#mcp adding

MCP_RESULT_TMPL = """
{% if result.isError %}
<div class="card"><p class="error">MCP call refused ({{ result.boundary }}): {{ result.content[0].text }}</p></div>
{% else %}
{% set data = result.structuredContent %}
<div class="card">
    <p class="muted">{{ result.content[0].text }}</p>
    {% for row in data.rows %}
    <div class="trip-card__footer">
        <strong>{{ row.destination }}</strong>
        <span class="muted"> &middot; {{ row.start_date }} &rarr; {{ row.end_date }} &middot; {{ row.travel_style }}</span>
    </div>
    {% else %}
    <p class="muted">No matches.</p>
    {% endfor %}
</div>
{% endif %}
"""

#rag tmpl
RAG_RESULT_TMPL = """
<div class="card">
<p><strong>{{ "AI Answer" if result.grounded else "No answer available" }}</strong></p>
<p>{{ result.answer }}</p>
<p class="muted">
    Confidence: <span class="pill pill-{{ result.confidence }}">{{ result.confidence }}</span>
</p>
{% if result.citations %}
    <div class="chat-log">
    {% for c in result.citations %}
        <p class="compat-reason">
        [{{ c.number }}] {{ c.source }} &gt; {{ c.section }} &mdash; {{ c.excerpt }}
        </p>
    {% endfor %}
    </div>
{% endif %}
</div>
"""
#Chat temp
CHAT_THREAD_TMPL = """
<div class="thread-slot" style="border:1px solid #ddd; border-radius:10px; padding:0.75rem; margin-top:0.75rem; background:#fafafa">
    <div class="chat-log" id="thread-{{ post_id }}-{{ other_id }}"
        style="max-height:260px; overflow-y:auto; display:flex; flex-direction:column; gap:0.5rem; padding-right:0.25rem">
    {% for msg in messages %}
        <div class="chat-msg {{ 'me' if msg.is_mine else 'bot' }}"
            style="align-self:{{ 'flex-end' if msg.is_mine else 'flex-start' }}; max-width:75%">
        <div class="who" style="font-size:0.7rem; color:#888">
            {{ "You" if msg.is_mine else (msg.other_party_name or "Traveller " ~ msg.from_traveller_id) }}
        </div>
        <div class="bubble" style="padding:0.5rem 0.75rem; border-radius:12px;
                background:{{ '#1e3a5f' if msg.is_mine else '#e9e9eb' }};
                color:{{ '#fff' if msg.is_mine else '#111' }};
                display:flex; align-items:center; gap:0.5rem">
            <span>{{ msg.message }}</span>
            {% if msg.is_mine %}
            <button class="btn-sm"
                    hx-delete="/api/student-3/connect/message/{{ msg.request_id }}/{{ post_id }}/{{ other_id }}"
                    hx-target="closest .thread-slot" hx-swap="outerHTML"
                    hx-confirm="Delete this message?"
                    style="background:transparent; border:none; color:#ffb4b4; cursor:pointer; font-size:0.8rem">
                ✕
                </button>
            {% endif %}
            </div>
            <div class="muted" style="font-size:0.65rem; margin-top:0.15rem">{{ msg.created_at }}</div>
        </div>
        {% else %}
        <p class="chat-log__empty">No messages yet. Say hello!</p>
    {% endfor %}
    </div>
    <form hx-post="/api/student-3/connect"
        hx-target="closest .thread-slot"
        hx-swap="outerHTML"
        hx-on::after-request="this.reset()"
        style="display:flex; gap:0.5rem; margin-top:0.5rem">
    <input type="hidden" name="to_post_id" value="{{ post_id }}">
    <input type="hidden" name="other_id" value="{{ other_id }}">
    <input name="message" placeholder="Type a message..." required style="flex:1">
    <button type="submit" class="btn-sm">Send</button>
</form>
</div>
"""


@app.get("/trips")
def browse_trips():
    params = {
        "destination": request.args.get("destination", ""),
        "status": "open",
    }
    r = requests.get(f"{DB_SERVICE_URL}/trip_posts", params=params, timeout=5)
    r.raise_for_status()
    posts = r.json()
    return render_template_string(TRIP_CARD_TMPL, posts=posts, current_id=CURRENT_TRAVELLER_ID)
@app.get("/trips/mine")
def my_trips():
    r = requests.get(
        f"{DB_SERVICE_URL}/trip_posts",
        params={"traveller_id": CURRENT_TRAVELLER_ID},
        timeout=5,
    )
    r.raise_for_status()
    posts = r.json()
    return render_template_string(TRIP_CARD_TMPL, posts=posts, current_id=CURRENT_TRAVELLER_ID)




@app.post("/trips")
def create_trip():
    form = request.form
    payload = {
        "traveller_id": CURRENT_TRAVELLER_ID,
        "destination": form.get("destination", ""),
        "start_date": form.get("start_date", ""),
        "end_date": form.get("end_date", ""),
        "travel_style": form.get("travel_style", ""),
        "note": form.get("note", ""),
        "status": "open",
    }
    r = requests.post(f"{DB_SERVICE_URL}/trip_posts", json=payload, timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">Could not post trip: {r.json().get("error", "unknown error")}</p>', 400
    response = app.make_response('<p class="success">Trip posted! Check the Browse tab.</p>')
    response.headers["HX-Trigger"] = "tripPosted"
    return response
@app.delete("/trips/<int:post_id>")
def delete_trip(post_id):
    r = requests.delete(f"{DB_SERVICE_URL}/trip_posts/{post_id}", timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">{r.json().get("error", "Delete failed")}</p>', 400
    return ""  # swap the card away entirely
def _fetch_post_or_error(post_id):
    r = requests.get(f"{DB_SERVICE_URL}/trip_posts/{post_id}", timeout=5)
    if r.status_code >= 400:
        return None, f'<p class="error">{r.json().get("error", "Trip post not found")}</p>'
    return r.json(), None

#del the chat
@app.delete("/connect/message/<int:request_id>/<int:post_id>/<int:other_id>")
def delete_own_message(request_id, post_id, other_id):
    r = requests.delete(f"{DB_SERVICE_URL}/connect_requests/{request_id}", timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">{r.json().get("error", "Delete failed")}</p>', 400
    return build_thread(post_id, other_id)




@app.get("/trips/<int:post_id>/edit")
def edit_trip_form(post_id):
    post, error_html = _fetch_post_or_error(post_id)
    if error_html:
        return error_html, 404
    return render_template_string(EDIT_FORM_TMPL, post=post)




@app.get("/trips/<int:post_id>/view")
def view_trip_card(post_id):
    post, error_html = _fetch_post_or_error(post_id)
    if error_html:
        return error_html, 404
    return render_template_string(TRIP_CARD_TMPL, posts=[post], current_id=CURRENT_TRAVELLER_ID)




@app.put("/trips/<int:post_id>")
def update_trip(post_id):
    form = request.form
    payload = {
        "destination": form.get("destination", ""),
        "start_date": form.get("start_date", ""),
        "end_date": form.get("end_date", ""),
        "travel_style": form.get("travel_style", ""),
        "note": form.get("note", ""),
    }
    r = requests.put(f"{DB_SERVICE_URL}/trip_posts/{post_id}", json=payload, timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">Could not update trip: {r.json().get("error", "unknown error")}</p>', 400
    updated_post = r.json()
    return render_template_string(TRIP_CARD_TMPL, posts=[updated_post], current_id=CURRENT_TRAVELLER_ID)


@app.post("/connect")
def say_hi():
    form_data = request.form or (request.get_json(silent=True) or {})
    to_post_id = int(form_data.get("to_post_id"))
    other_id = form_data.get("other_id")

    payload = {
        "from_traveller_id": CURRENT_TRAVELLER_ID,
        "to_post_id": to_post_id,
        "message": form_data.get("message", "Hi! Would love to join your trip."),
        "status": "pending",
    }
    r = requests.post(f"{DB_SERVICE_URL}/connect_requests", json=payload, timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">{r.json().get("error", "Could not send request")}</p>', 400

    if other_id is None:
        post = requests.get(f"{DB_SERVICE_URL}/trip_posts/{to_post_id}", timeout=5).json()
        other_id = post["traveller_id"]
    other_id = int(other_id)

    return build_thread(to_post_id, other_id)




@app.get("/connect/incoming")
def incoming_requests():
    r = requests.get(f"{DB_SERVICE_URL}/connect_requests", timeout=5)
    r.raise_for_status()
    all_reqs = r.json()

    posts_r = requests.get(f"{DB_SERVICE_URL}/trip_posts", params={"traveller_id": CURRENT_TRAVELLER_ID}, timeout=5)
    my_posts = {p["post_id"]: p for p in posts_r.json()}
    my_post_ids = set(my_posts.keys())

    incoming = [r_ for r_ in all_reqs if r_["to_post_id"] in my_post_ids]

    for req in incoming:
        traveller = get_traveller(req["from_traveller_id"])
        req["other_party_name"] = traveller["full_name"] if traveller else None
        req["destination"] = my_posts.get(req["to_post_id"], {}).get("destination")

    return render_template_string(REQUEST_ROW_TMPL, requests=incoming, direction="incoming")



    for req in incoming:
        traveller = get_traveller(req["from_traveller_id"])
        req["sender_name"] = traveller["full_name"] if traveller else None
        req["destination"] = my_posts.get(req["to_post_id"], {}).get("destination")


    return render_template_string(REQUEST_ROW_TMPL, requests=incoming, direction="incoming")
@app.get("/connect/outgoing")
def outgoing_requests():
    r = requests.get(
        f"{DB_SERVICE_URL}/connect_requests",
        params={"from_traveller_id": CURRENT_TRAVELLER_ID},
        timeout=5,
    )
    r.raise_for_status()
    outgoing = r.json()


    for req in outgoing:
        post_r = requests.get(f"{DB_SERVICE_URL}/trip_posts/{req['to_post_id']}", timeout=5)
        if post_r.status_code == 200:
            post = post_r.json()
            owner = get_traveller(post["traveller_id"])
            req["other_party_name"] = owner["full_name"] if owner else None
            req["destination"] = post["destination"]
        else:
            req["other_party_name"] = None
            req["destination"] = None


    return render_template_string(REQUEST_ROW_TMPL, requests=outgoing, direction="outgoing")




@app.put("/connect/<int:request_id>")
def update_request(request_id):
    payload = request.get_json(silent=True) or dict(request.form)
    r = requests.put(f"{DB_SERVICE_URL}/connect_requests/{request_id}", json=payload, timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">{r.json().get("error", "Update failed")}</p>', 400
    updated = [r.json()]
    return render_template_string(REQUEST_ROW_TMPL, requests=updated, direction="incoming")




@app.delete("/connect/<int:request_id>")
def withdraw_request(request_id):
    r = requests.delete(f"{DB_SERVICE_URL}/connect_requests/{request_id}", timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">{r.json().get("error", "Withdraw failed")}</p>', 400
    return "" 

# --- AI Integration: match-suggest (Plan -> Act -> Observe -> Adapt) -------
# The loop itself is in agentic_loop/core/orchestrator.py.
@app.post("/ai/match-suggest")
def match_suggest():
    question = request.form.get("question", "")
    try:
        result = run_match_turn(question, CURRENT_TRAVELLER_ID)
    except requests.RequestException as exc:
        return f'<div class="card"><p class="error">Could not reach the database service: {exc}</p></div>', 502
    return match_fragment(result)


@app.post("/trips/ai-score")
def ai_score_trips():
    destination = request.form.get("destination", "")
    params = {"destination": destination, "status": "open"}
    r = requests.get(f"{DB_SERVICE_URL}/trip_posts", params=params, timeout=5)
    r.raise_for_status()
    posts = r.json()

    my_posts_r = requests.get(
        f"{DB_SERVICE_URL}/trip_posts",
        params={"traveller_id": CURRENT_TRAVELLER_ID, "status": "open"},
        timeout=5,
    )
    my_posts = my_posts_r.json()

    scores = {}
    note = ""

    if not my_posts:
        note = "Post a trip first to see AI compatibility scores."
    else:
    
        if destination:
            dest_lower = destination.lower()
            my_post = next(
                (p for p in my_posts if dest_lower in p["destination"].lower()),
                my_posts[0],
            )
        else:
            my_post = my_posts[0]

        candidates = [p for p in posts if p["post_id"] != my_post["post_id"]]
        if not candidates:
            note = "No other open trips to compare yet."
        else:
            try:
                matches = score_candidates(
                                    my_post, candidates, "General browsing compatibility check."
                )

                scores = {m["post_id"]: m for m in matches if "post_id" in m}
            except LLM_ERRORS as exc:
                note = f"AI scoring unavailable right now ({exc})."

    cards_html = render_template_string(
        TRIP_CARD_TMPL, posts=posts, current_id=CURRENT_TRAVELLER_ID, scores=scores
    )
    if note:
        cards_html += f'<p class="muted">{note}</p>'
    return cards_html

#mcp integration

@app.post("/mcp/find-mates")
def mcp_find_mates():
    if not MCP_ENABLED:
        return '<div class="card"><p class="error">MCP integration is disabled in this environment.</p></div>', 503
    destination = request.form.get("destination", "")
    args = {"destination": destination} if destination else {}
    try:
        result = call_mcp_tool("find_travel_mates", args)
    except (requests.RequestException, ValueError) as exc:
        return f'<div class="card"><p class="error">MCP request failed: {exc}</p></div>', 502
    return render_template_string(MCP_RESULT_TMPL, result=result)

# rag integration
@app.post("/ai/ask-grounded")
def ask_grounded():
    if not RAG_ENABLED:
        return '<div class="card"><p class="error">RAG integration is disabled in this environment.</p></div>', 503
    question = request.form.get("question", "")
    if not question.strip():
        return '<div class="card"><p class="error">Type a question first.</p></div>', 400
    try:
        result = call_rag_ask(question)
    except requests.RequestException as exc:
        return f'<div class="card"><p class="error">RAG request failed: {exc}</p></div>', 502
    return render_template_string(RAG_RESULT_TMPL, result=result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5103)))






##### ./scripts/dev.sh up

