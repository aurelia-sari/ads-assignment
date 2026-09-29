"""ACT step: gather real trip data from the db service. No LLM involved."""

from services import database_api

def _rows(response):
    return response.json() if response.status_code == 200 else []


def collect_my_open_posts(traveller_id):
    return _rows(database_api.get_trip_posts(traveller_id=traveller_id, status="open"))
    
    
def collect_all_open_posts():
    return _rows(database_api.get_trip_posts(status="open"))

def collect_candidates(my_posts, all_open_posts, destination_hint):
    """Pick the traveller's own post and the posts worth comparing it to."""
    if destination_hint:
        hint = destination_hint.lower()
        my_post = next((p for p in my_posts if hint in p["destination"].lower()), my_posts[0])
        candidates = [
            c for c in all_open_posts
            if hint in c["destination"].lower() and c["post_id"] != my_post["post_id"]
        ]
    else:
        my_post = my_posts[0]
        candidates = [
            c for c in all_open_posts
            if c["destination"] == my_post["destination"] and c["post_id"] != my_post["post_id"]
        ]
    return my_post, candidates