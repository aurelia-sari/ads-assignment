"""Plan -> Act -> Observe -> Adapt loop for Travel Mate matching.
 
The code gathers the evidence; the LLM only scores what was fetched.
"""
 
import json
 
import requests
 
from agentic_loop.collectors.trip_collector import (
    collect_all_open_posts,
    collect_candidates,
    collect_my_open_posts,
)
from agentic_loop.core.classifier import extract_destination_hint
from services.ai_client import ask_ai
from services.prompt_loader import load_prompt
 
HIGH_SCORE = 60
LLM_ERRORS = (requests.RequestException, ValueError, json.JSONDecodeError, KeyError)
 
 
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
 
 
def score_candidates(my_post, candidates, question, ask=ask_ai):
    """The only place the LLM is called. Returns a list of match dicts."""
    prompt = build_match_prompt(my_post, candidates, question)
    raw_text = ask(prompt, load_prompt("implementation", "match_system.txt"), max_tokens=500)
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
 
 
def run(question, traveller_id):
    """One matching turn. Returns a dict with a `status` the view renders."""
    
    # PLAN: 
    my_posts = collect_my_open_posts(traveller_id)
    if not my_posts:
        return {"status": "no_own_post"}
    all_open = collect_all_open_posts()
    hint = extract_destination_hint(question, all_open)
 
    # ACT: 
    my_post, candidates = collect_candidates(my_posts, all_open, hint)
 
    # ADAPT 
    adapted = False
    if not candidates:
        if hint:
            return {"status": "no_candidates_for_destination", "hint": hint}
        adapted = True
        candidates = [c for c in all_open if c["post_id"] != my_post["post_id"]]
    if not candidates:
        return {"status": "no_candidates"}
 
    try:
        matches = score_candidates(my_post, candidates, question)
    except LLM_ERRORS as exc:
        return {"status": "error", "error": str(exc)}
 
    # OBSERVE: 
    high_confidence = [m for m in matches if m.get("score", 0) >= HIGH_SCORE]
    by_id = {c["post_id"]: c for c in candidates}
    ranked = sorted(matches, key=lambda m: m.get("score", 0), reverse=True)
 
    return {
        "status": "ok",
        "matches": [(by_id[m["post_id"]], m) for m in ranked if m.get("post_id") in by_id],
        "adapted": adapted,
        "low_confidence": not high_confidence,
    }