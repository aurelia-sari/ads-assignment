"""Travel Mate backend/API microservice (student-3, Tanishpreet Kour).
 
Sits between the frontend (index.html) and the database microservice
(student-3/db/app.py, default http://localhost:5203). Never touches
student3.db directly -- all data access goes through the db service's
REST API, per the "each database container owns its schema" rule in the
project spec.
 
Also serves the frontend's index.html at "/" so you can test the whole
feature from one URL locally: http://localhost:5103/
"""
 
import os
 
import requests
from flask import Flask, jsonify, render_template_string, request, send_from_directory
 
app = Flask(__name__)
 
DB_SERVICE_URL = os.environ.get("DB_SERVICE_URL", "http://localhost:5203")
FRONTEND_DIR = os.environ.get("FRONTEND_DIR", "../frontend/templates")  # adjust to your repo layout
 
# The "logged-in" traveller for this local/dev build. Swap for real auth
# (Feature 5, student-5) once that's integrated.
CURRENT_TRAVELLER_ID = int(os.environ.get("CURRENT_TRAVELLER_ID", "1"))
 
 
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
<div class="card">
  <div class="trip-card__header">
    <div>
      <span class="trip-card__destination">{{ post.destination }}</span>
      <div class="trip-card__dates">{{ post.start_date }} &rarr; {{ post.end_date }}</div>
    </div>
    <span class="pill pill-planned">{{ post.travel_style }}</span>
  </div>
  <p class="trip-card__note">{{ post.note }}</p>
  <div class="trip-card__footer">
    <span class="compat-score"><span class="compat-score__num">--</span></span>
    <button class="say-hi-btn" hx-post="/api/student-3/connect"
            hx-vals='{"to_post_id": {{ post.post_id }}}'
            hx-target="closest .card" hx-swap="outerHTML"
            {% if post.traveller_id == current_id %}disabled{% endif %}>
      Say Hi
    </button>
  </div>
</div>
{% else %}
<p class="muted">No trips match those filters yet.</p>
{% endfor %}
"""
 
REQUEST_ROW_TMPL = """
{% for r in requests %}
<div class="request-row">
  <div>
    <strong>{{ r.destination or ('Post #' ~ r.to_post_id) }}</strong>
    <div class="request-row__meta">{{ r.message }} &middot; {{ r.created_at }}</div>
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
    {% endif %}
  </div>
</div>
{% else %}
<p class="muted">Nothing here yet.</p>
{% endfor %}
"""
 
 
# --- Trips (browse / post / mine) -------------------------------------------
 
@app.get("/api/student-3/trips")
def browse_trips():
    params = {
        "destination": request.args.get("destination", ""),
        "status": "open",
    }
    r = requests.get(f"{DB_SERVICE_URL}/trip_posts", params=params, timeout=5)
    r.raise_for_status()
    posts = r.json()
    return render_template_string(TRIP_CARD_TMPL, posts=posts, current_id=CURRENT_TRAVELLER_ID)
 
 
@app.get("/api/student-3/trips/mine")
def my_trips():
    r = requests.get(
        f"{DB_SERVICE_URL}/trip_posts",
        params={"traveller_id": CURRENT_TRAVELLER_ID},
        timeout=5,
    )
    r.raise_for_status()
    posts = r.json()
    return render_template_string(TRIP_CARD_TMPL, posts=posts, current_id=CURRENT_TRAVELLER_ID)
 
 
@app.post("/api/student-3/trips")
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
    return '<p class="success">Trip posted! Check the Browse tab.</p>'
 
 
# --- Connect requests (say hi / accept / decline / withdraw) ---------------
 
@app.post("/api/student-3/connect")
def say_hi():
    to_post_id = request.form.get("to_post_id") or (request.get_json(silent=True) or {}).get("to_post_id")
    payload = {
        "from_traveller_id": CURRENT_TRAVELLER_ID,
        "to_post_id": to_post_id,
        "message": request.form.get("message", "Hi! Would love to join your trip."),
        "status": "pending",
    }
    r = requests.post(f"{DB_SERVICE_URL}/connect_requests", json=payload, timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">{r.json().get("error", "Could not send request")}</p>', 400
    return '<button class="say-hi-btn" disabled>Requested</button>'
 
 
@app.get("/api/student-3/connect/incoming")
def incoming_requests():
    r = requests.get(f"{DB_SERVICE_URL}/connect_requests", timeout=5)
    r.raise_for_status()
    all_reqs = r.json()
    # incoming = requests where the post belongs to me
    posts_r = requests.get(f"{DB_SERVICE_URL}/trip_posts", params={"traveller_id": CURRENT_TRAVELLER_ID}, timeout=5)
    my_post_ids = {p["post_id"] for p in posts_r.json()}
    incoming = [r_ for r_ in all_reqs if r_["to_post_id"] in my_post_ids]
    return render_template_string(REQUEST_ROW_TMPL, requests=incoming, direction="incoming")
 
 
@app.get("/api/student-3/connect/outgoing")
def outgoing_requests():
    r = requests.get(
        f"{DB_SERVICE_URL}/connect_requests",
        params={"from_traveller_id": CURRENT_TRAVELLER_ID},
        timeout=5,
    )
    r.raise_for_status()
    return render_template_string(REQUEST_ROW_TMPL, requests=r.json(), direction="outgoing")
 
 
@app.put("/api/student-3/connect/<int:request_id>")
def update_request(request_id):
    payload = request.get_json(silent=True) or dict(request.form)
    r = requests.put(f"{DB_SERVICE_URL}/connect_requests/{request_id}", json=payload, timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">{r.json().get("error", "Update failed")}</p>', 400
    updated = [r.json()]
    return render_template_string(REQUEST_ROW_TMPL, requests=updated, direction="incoming")
 
 
@app.delete("/api/student-3/connect/<int:request_id>")
def withdraw_request(request_id):
    r = requests.delete(f"{DB_SERVICE_URL}/connect_requests/{request_id}", timeout=5)
    if r.status_code >= 400:
        return f'<p class="error">{r.json().get("error", "Withdraw failed")}</p>', 400
    return ""  # swap the row away entirely
 
 
# --- AI Integration: match-suggest (Plan -> Act -> Observe -> Adapt) -------
 
@app.post("/api/student-3/ai/match-suggest")
def match_suggest():
    """
    PLAN:    read the user's own open post + their free-text question.
    ACT:     fetch candidate posts from the db service, send both to the LLM.
    OBSERVE: check whether the LLM returned any high-confidence matches.
    ADAPT:   if none, widen the search (drop date filter) and re-ask.
    """
    question = request.form.get("question", "")
 
    my_posts_r = requests.get(
        f"{DB_SERVICE_URL}/trip_posts", params={"traveller_id": CURRENT_TRAVELLER_ID, "status": "open"}, timeout=5
    )
    my_posts = my_posts_r.json()
    if not my_posts:
        return '<p class="chat-log__empty">Post a trip first so the AI has something to match against.</p>'
 
    my_post = my_posts[0]
 
    candidates_r = requests.get(
        f"{DB_SERVICE_URL}/trip_posts", params={"destination": my_post["destination"], "status": "open"}, timeout=5
    )
    candidates = [c for c in candidates_r.json() if c["post_id"] != my_post["post_id"]]
 
    # OBSERVE: no candidates for the exact destination -> ADAPT by widening
    adapted = False
    if not candidates:
        adapted = True
        candidates_r = requests.get(f"{DB_SERVICE_URL}/trip_posts", params={"status": "open"}, timeout=5)
        candidates = [c for c in candidates_r.json() if c["post_id"] != my_post["post_id"]]
 
    # --- Call Ollama here (replace with your actual endpoint) ---
    # ollama_resp = requests.post(
    #     "http://localhost:11434/api/generate",
    #     json={
    #         "model": "qwen2.5",
    #         "prompt": build_match_prompt(my_post, candidates, question),
    #         "stream": False,
    #     },
    #     timeout=30,
    # )
    # reasoning = ollama_resp.json()["response"]
    reasoning = (
        f"(placeholder — wire up Ollama here) Comparing your {my_post['travel_style']} trip to "
        f"{my_post['destination']} against {len(candidates)} candidate post(s)."
    )
 
    note = " Widened the search since no matches were found for your exact destination." if adapted else ""
    return f'<div class="card"><p>{reasoning}{note}</p></div>'
 
 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5103)))