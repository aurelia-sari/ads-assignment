"""PLAN helper: work out which destination a question is about."""
    
    
def extract_destination_hint(question, all_open_posts):
    """Return the matching keyword itself (e.g. "iceland"), not a specific
    post's destination string, so substring matching finds every post that
    mentions it however the destination is formatted."""
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
    return max(matched, key=len)