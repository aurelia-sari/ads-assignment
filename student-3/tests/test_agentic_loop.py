"""Unit tests for the Travel Mate Plan -> Act -> Observe -> Adapt loop.

The database and the model are stubbed; nothing here touches the network.

    python -m pytest student-3/tests/agentic_loop.py
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from agentic_loop.collectors import trip_collector 
from agentic_loop.core import orchestrator 
from agentic_loop.core.classifier import extract_destination_hint  
from views.ai_formatter import match_fragment  


def post(post_id, destination, traveller_id=1):
    return {"post_id": post_id, "traveller_id": traveller_id, "destination": destination,
            "start_date": "2026-10-01", "end_date": "2026-10-08",
            "travel_style": "hiking", "note": "n"}


BALI, KYOTO, LISBON, BALI2 = (post(1, "Bali, Indonesia"), post(2, "Kyoto, Japan", 2),
                              post(3, "Lisbon, Portugal", 3), post(4, "Bali, Indonesia", 4))


# PLAN: destination hint

def test_hint_is_the_longest_matching_keyword():
    assert extract_destination_hint("hikers in Bali, Indonesia?", [BALI, KYOTO]) == "bali, indonesia" or \
           extract_destination_hint("hikers in Bali, Indonesia?", [BALI, KYOTO]) in ("bali", "indonesia")


def test_hint_is_none_when_no_destination_is_named():
    assert extract_destination_hint("find me someone fun", [BALI, KYOTO]) is None


def test_hint_is_none_for_an_empty_question():
    assert extract_destination_hint("", [BALI]) is None


# ACT: candidate selection

def test_candidates_follow_the_hint_and_exclude_my_post():
    my_post, candidates = trip_collector.collect_candidates([BALI], [BALI, BALI2, KYOTO], "bali")
    assert my_post == BALI
    assert [c["post_id"] for c in candidates] == [4]


def test_without_a_hint_candidates_share_my_destination():
    _, candidates = trip_collector.collect_candidates([BALI], [BALI, BALI2, KYOTO], None)
    assert [c["post_id"] for c in candidates] == [4]


# Scoring: tolerant of the shapes a small model returns

def ask_returning(payload):
    return lambda prompt, system, max_tokens=500: payload


def test_score_accepts_a_json_array():
    raw = json.dumps([{"post_id": 4, "score": 80, "reason": "same place"}])
    assert orchestrator.score_candidates(BALI, [BALI2], "q", ask=ask_returning(raw))[0]["score"] == 80


def test_score_unwraps_an_object_holding_a_list():
    raw = json.dumps({"matches": [{"post_id": 4, "score": 70, "reason": "r"}]})
    assert orchestrator.score_candidates(BALI, [BALI2], "q", ask=ask_returning(raw))[0]["post_id"] == 4


def test_score_accepts_a_single_match_object():
    raw = json.dumps({"post_id": 4, "score": 55, "reason": "r"})
    assert len(orchestrator.score_candidates(BALI, [BALI2], "q", ask=ask_returning(raw))) == 1


def test_score_rejects_an_empty_list():
    with pytest.raises(ValueError):
        orchestrator.score_candidates(BALI, [BALI2], "q", ask=ask_returning("[]"))


def test_score_rejects_unrecognised_json():
    with pytest.raises(ValueError):
        orchestrator.score_candidates(BALI, [BALI2], "q", ask=ask_returning('{"nothing": 1}'))


# The whole loop

@pytest.fixture
def world(monkeypatch):
    def install(mine, everything):
        monkeypatch.setattr(orchestrator, "collect_my_open_posts", lambda traveller_id: mine)
        monkeypatch.setattr(orchestrator, "collect_all_open_posts", lambda: everything)
    return install


def test_no_own_post(world):
    world([], [KYOTO])
    assert orchestrator.run("anyone?", 1) == {"status": "no_own_post"}


def test_named_destination_with_nobody_there(world, monkeypatch):
    world([BALI], [BALI, LISBON])

    def must_not_score(*args, **kwargs):
        raise AssertionError("should not reach the model")

    monkeypatch.setattr(orchestrator, "score_candidates", must_not_score)
    result = orchestrator.run("anyone going to Bali?", 1)
    assert result["status"] == "no_candidates_for_destination"
    assert result["hint"] == "bali"


def test_adapt_widens_the_search_when_no_destination_is_named(world, monkeypatch):
    world([BALI], [BALI, KYOTO, LISBON])
    monkeypatch.setattr(orchestrator, "score_candidates", lambda my, cands, q: [
        {"post_id": c["post_id"], "score": 40, "reason": "r"} for c in cands])
    result = orchestrator.run("find me a buddy", 1)
    assert result["status"] == "ok"
    assert result["adapted"] is True
    assert result["low_confidence"] is True


def test_matches_are_ranked_and_confidence_is_observed(world, monkeypatch):
    world([BALI], [BALI, BALI2, KYOTO])
    monkeypatch.setattr(orchestrator, "score_candidates", lambda my, cands, q: [
        {"post_id": 4, "score": 90, "reason": "same trip"}])
    result = orchestrator.run("hikers in Bali", 1)
    assert result["status"] == "ok"
    assert result["low_confidence"] is False
    assert result["matches"][0][0]["post_id"] == 4


def test_model_failure_is_reported_not_raised(world, monkeypatch):
    world([BALI], [BALI, BALI2])

    def boom(*args, **kwargs):
        raise ValueError("not json")

    monkeypatch.setattr(orchestrator, "score_candidates", boom)
    result = orchestrator.run("hikers in Bali", 1)
    assert result["status"] == "error"


# The view: everything from the DB or model is escaped

def test_fragment_escapes_model_output():
    html = match_fragment({
        "status": "ok", "adapted": False, "low_confidence": False,
        "matches": [({"destination": "<b>Bali</b>"}, {"score": 90, "reason": "<script>x</script>"})]})
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_fragment_for_no_own_post_prompts_the_user():
    assert "Post a trip first" in match_fragment({"status": "no_own_post"})