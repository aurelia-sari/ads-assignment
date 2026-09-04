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
import requests
from flask import Flask, jsonify, render_template_string, request, send_from_directory
app = Flask(__name__)
DB_SERVICE_URL = os.environ.get("DB_SERVICE_URL", "http://localhost:5203")
FRONTEND_DIR = os.environ.get("FRONTEND_DIR", "../frontend/templates")  # adjust to your repo layout
# The "logged-in" traveller for this local/dev build. Swap for real auth
# (Feature 5, student-5) once that's integrated.
CURRENT_TRAVELLER_ID = int(os.environ.get("CURRENT_TRAVELLER_ID", "1"))
#newly addeddddddddddd just some experimeting
SHARED_DB_URL = os.environ.get("SHARED_DB_URL", "http://localhost:5200")




def get_traveller(traveller_id):
    """Best-effort lookup of a traveller's display name from shared-db.
    Returns None on any failure so a down shared-db never breaks Inbox."""
    try:
        r = requests.get(f"{SHARED_DB_URL}/travellers/{traveller_id}", timeout=3)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None
#OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
#OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


AI_MODE_URL = os.environ.get("AI_MODE_URL", "http://ai-mode:5300")
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
    <p class="trip-card__note">{{ post.note }}</p>
    {% set s = (scores|default({})).get(post.post_id) %}
    <div class="trip-card__footer">
    <span class="compat-score"><span class="compat-score__num">{% if s %}{{ s.score }}%{% else %}--{% endif %}</span></span>
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
                hx-vals='{"to_post_id": {{ post.post_id }}}'
                hx-target="closest .card" hx-swap="outerHTML">
        Say Hi
        </button>
    {% endif %}
    </div>
    {% if s and s.reason %}<span class="compat-reason">{{ s.reason }}</span>{% endif %}
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
   return ""  # swap the row away entirely

# --- AI Integration: match-suggest (Plan -> Act -> Observe -> Adapt) -------
def build_match_prompt(my_post, candidates, question):
   candidate_lines = "\n".join(
       f'- post_id={c["post_id"]}: destination="{c["destination"]}", '
       f'dates={c["start_date"]} to {c["end_date"]}, '
       f'travel_style="{c["travel_style"]}", note="{c["note"]}"'
       for c in candidates
   )
   return (
       "You are a travel-companion matching assistant for a travel app. "
       "Compare the user's own trip post against each candidate post below "
       "and score how compatible they'd be as travel companions.\n\n"
       f"User's question: {question}\n\n"
       f"User's own post: destination=\"{my_post['destination']}\", "
       f"dates={my_post['start_date']} to {my_post['end_date']}, "
       f"travel_style=\"{my_post['travel_style']}\", note=\"{my_post['note']}\"\n\n"
       f"Candidate posts:\n{candidate_lines}\n\n"
       f"There are exactly {len(candidates)} candidate post(s) listed above. "
       f"You MUST include exactly {len(candidates)} entries in your response "
       "array, one per candidate, in the same order they were listed -- "
       "do not skip any and do not return only your single favourite. "
       "Score each candidate on destination overlap, date overlap, and "
       "similarity of travel_style/note. Respond with ONLY a JSON array, "
       "no other text, in this exact shape:\n"
       '[{"post_id": <int>, "score": <int 0-100>, "reason": "<one short sentence>"}]'
   )
def call_ollama_match(my_post, candidates, question):
   prompt = build_match_prompt(my_post, candidates, question)
   resp = requests.post(
       f"{AI_MODE_URL}/recommend",
       json={
           "question": prompt,
           "system": (
               "You are a JSON API. Respond with ONLY valid JSON, "
               "no markdown code fences, no explanation, no other text."
           ),
           "max_tokens": 500,
       },
       timeout=180,
   )
   resp.raise_for_status()
   raw_text = resp.json()["answer"]
   print(f"[ai-mode raw response] {raw_text!r}") 
   parsed = json.loads(raw_text)
   if isinstance(parsed, list):
       matches = parsed
   elif isinstance(parsed, dict):
       list_values = [v for v in parsed.values() if isinstance(v, list)]
       if list_values:
           matches = list_values[0]
       elif "post_id" in parsed:
           matches = [parsed]
       else:
           raise ValueError(f"Unrecognised JSON shape from model: {parsed!r}")
   else:
       raise ValueError(f"Model did not return JSON array or object: {parsed!r}")
   if not matches:
       raise ValueError("Model returned an empty match list")
   return matches
def extract_destination_hint(question, all_open_posts):
   """
   Returns the matching keyword itself (e.g. "iceland" or "vietnam"),
   not a specific post's destination string -- candidate matching then
   uses substring containment, so this one keyword correctly matches
   every post whose destination mentions it, however that post's
   destination happens to be formatted ("Reykjavik, Iceland" or just
   "iceland").
   """
   if not question:
       return None
   question_lower = question.lower()
   tokens = set()
   for post in all_open_posts:
       for part in post["destination"].split(","):
           part = part.strip().lower()
           if part:
               tokens.add(part)
   matched = [t for t in tokens if t in question_lower]
   if not matched:
       return None
   return max(matched, key=len)  # prefer the more specific/longer match
@app.post("/ai/match-suggest")
def match_suggest():
   """
   PLAN:    read the user's own open post(s) + their free-text question,
            and try to detect a destination the question is actually about.
   ACT:     fetch candidate posts from the db service, send both to the LLM.
   OBSERVE: check whether the LLM returned any high-confidence matches.
   ADAPT:   if none, widen the search (drop destination filter) and re-ask.
   """
   question = request.form.get("question", "")
   my_posts_r = requests.get(
       f"{DB_SERVICE_URL}/trip_posts",
       params={"traveller_id": CURRENT_TRAVELLER_ID, "status": "open"},
       timeout=5,
   )
   my_posts = my_posts_r.json()
   if not my_posts:
       return '<p class="chat-log__empty">Post a trip first so the AI has something to match against.</p>'
   all_open_r = requests.get(
       f"{DB_SERVICE_URL}/trip_posts", params={"status": "open"}, timeout=5
   )
   all_open_posts = all_open_r.json()
   destination_hint = extract_destination_hint(question, all_open_posts)
   if destination_hint:
       hint_lower = destination_hint.lower()
       matching_own_post = next(
           (p for p in my_posts if hint_lower in p["destination"].lower()), None
       )
       my_post = matching_own_post or my_posts[0]
       candidates = [
           c for c in all_open_posts
           if hint_lower in c["destination"].lower() and c["post_id"] != my_post["post_id"]
       ]
   else:
       my_post = my_posts[0]
       candidates = [
           c for c in all_open_posts
           if c["destination"] == my_post["destination"] and c["post_id"] != my_post["post_id"]
       ]
   adapted = False
   if not candidates:
       if destination_hint:
           return (
               f'<div class="card"><p>No one else has an open trip post to '
               f'<strong>{destination_hint}</strong> right now. '
               "Check back later, or try asking about a different destination.</p></div>"
           )
       adapted = True
       candidates = [c for c in all_open_posts if c["post_id"] != my_post["post_id"]]
   if not candidates:
       return '<div class="card"><p>No other open trip posts to compare against yet.</p></div>'
   candidates_by_id = {c["post_id"]: c for c in candidates}
   try:
       matches = call_ollama_match(my_post, candidates, question)
   except (requests.RequestException, ValueError, json.JSONDecodeError, KeyError) as exc:
       return (
           f'<div class="card"><p class="error">AI request failed: {exc}. '
           "Is Ollama running with the model pulled?</p></div>"
       )
   high_confidence = [m for m in matches if m.get("score", 0) >= 60]
   widen_note = (
       " Widened the search since no matches were found for your exact destination."
       if adapted else ""
   )
   low_confidence_note = (
       " No strong matches found — try widening your dates or travel style."
       if not high_confidence else ""
   )
   rows = []
   for m in sorted(matches, key=lambda x: x.get("score", 0), reverse=True):
       candidate = candidates_by_id.get(m.get("post_id"))
       if not candidate:
           continue
       rows.append(
           f'<div class="chat-msg bot"><div class="who">Travel Mate AI</div>'
           f'<div class="bubble"><strong>{candidate["destination"]}</strong> '
           f'<span class="compat-score"><span class="compat-score__num">{m.get("score", "?")}%</span></span>'
           f'<span class="compat-reason">{m.get("reason", "")}</span></div></div>'
       )
   return "".join(rows) + f'<p class="muted">{widen_note}{low_confidence_note}</p>'
# --- AI scoring for Browse cards (button-triggered) -------------------------


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
        # NEW: pick the post that matches the current destination filter,
        # falling back to the first post only if nothing matches.
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
                matches = call_ollama_match(
                    my_post, candidates, "General browsing compatibility check."
                )
                scores = {m["post_id"]: m for m in matches if "post_id" in m}
            except (requests.RequestException, ValueError, json.JSONDecodeError, KeyError) as exc:
                note = f"AI scoring unavailable right now ({exc})."

    cards_html = render_template_string(
        TRIP_CARD_TMPL, posts=posts, current_id=CURRENT_TRAVELLER_ID, scores=scores
    )
    if note:
        cards_html += f'<p class="muted">{note}</p>'
    return cards_html
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5103)))






##### ./scripts/dev.sh up

