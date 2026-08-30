def validate_recommendation(answer, candidates):
    candidate_names = [
        place["name"]
        for place in candidates
    ]

    matched_names = [
        name
        for name in candidate_names
        if name in answer
    ]

    return {
        "valid": len(matched_names) > 0,
        "place_names": matched_names,
    }