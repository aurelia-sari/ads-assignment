"""Offline contract tests: real shared server/store, mocked AI and MCP transport.

Run from the repository root: python -B student-2/tests/test_agents.py
Temporary persistence is confined to student-2/tests and removed automatically.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
from app import app
from services import multi_agent_client as client
from services import mcp_client, place_evidence

shared = ROOT.parent / "ai-services" / "multi-agent-server"
sys.path.insert(0, str(shared))
spec = importlib.util.spec_from_file_location("shared_multi_agent_server", shared / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class AgentsContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agents-test-", dir=ROOT / "tests")
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name)
        for name, value in {"DATA_DIR": directory, "WORKFLOW_DIR": directory / "workflows", "AUDIT_LOG": directory / "audit.jsonl"}.items():
            p = patch.object(server.store, name, value)
            p.start(); self.addCleanup(p.stop)
        self.web = app.test_client()
        self.shared_web = server.app.test_client()
        env = patch.dict(os.environ, {"MULTI_AGENT_ENABLED": "true", "MULTI_AGENT_URL": "http://shared-test:5600"})
        env.start(); self.addCleanup(env.stop)
        plan = {"goal": "Sydney day out", "steps": ["Read places", "Recommend"], "required_evidence": ["S1", "S2", "S3"], "acceptance_criteria": ["Cite evidence"]}
        review = {"verdict": "pass", "criteria": [{"criterion": "Cite evidence", "met": True, "note": "Cited E1"}], "risks": [], "recommendations": ["Verify opening hours"]}
        def model_reply(system, content, max_tokens):
            if "Evidence sources available:" in content:
                return json.dumps(plan), "test-model"
            if "Worker response:" in content:
                return json.dumps(review), "test-model"
            import re
            lines = ["| Place | City | Opening hours | Reason | Evidence |", "| --- | --- | --- | --- | --- |"]
            for match in re.finditer(r"\[(E\d+)\][^\n]*\n(\{[^\n]*\})", content):
                for row in json.loads(match[2])["places"]:
                    lines.append(f"| {row['name']} | {row['city']} | {row['opening_hours']} | {row['recommendation_reason']} | [{match[1]}] |")
            return "\n".join(lines), "test-model"
        model = patch.object(server.agents, "ask_ai_mode", side_effect=model_reply)
        model.start(); self.addCleanup(model.stop)
        def places(category, name=None):
            names = {"attraction": "Sydney Opera House", "restaurant": "Bourke Street Bakery", "activity": "Sydney Harbour Kayak"}
            row = {"name": name or names[category], "category": category, "address": "Sydney NSW", "latitude": -33.85, "longitude": 151.2, "opening_hours": "09:00-17:00", "rating": 4.8, "image_url": "https://example.test/" + "x"*5000}
            other = {**row, "name": "Melbourne Skydeck", "address": "Melbourne VIC", "latitude": -37.82, "longitude": 144.96}
            return {"structuredContent": {"rows": [row, other]}}
        mcp = patch.object(mcp_client, "search_places", side_effect=places)
        self.mcp = mcp.start(); self.addCleanup(mcp.stop)
        transport = patch.object(client.requests, "request", side_effect=self.transport)
        self.transport = transport.start(); self.addCleanup(transport.stop)

    def transport(self, method, url, json=None, timeout=None):
        parts = urlsplit(url)
        response = self.shared_web.open(parts.path + ("?" + parts.query if parts.query else ""), method=method, json=json)
        return Mock(status_code=response.status_code, json=lambda: response.get_json())

    def start(self, category="all"):
        response = self.web.post("/agents/workflows", json={"task": "Plan Sydney attractions and dining", "city": "Sydney", "category": category})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_real_pipeline_and_tool_contract(self):
        w = self.start()
        self.assertEqual(w["feature"], "student-2")
        self.assertEqual(w["status"], "awaiting_human_review")
        self.assertIsNone(w["final_response"])
        self.assertTrue(all(s["kind"] == "supplied" for s in w["sources"]))
        self.assertTrue(w["student2_validation"]["can_accept"])
        offered = [row["category"] for source in w["sources"] for row in json.loads(source["content"])["places"]]
        self.assertEqual(offered, ["attraction", "restaurant", "activity"])
        self.assertEqual(w["student2_validation"]["covered_categories"], ["activity", "attraction", "restaurant"])
        self.assertTrue(all("Melbourne" not in s["content"] and "image_url" not in s["content"] and len(s["content"]) < 2000 for s in w["sources"]))
        self.assertEqual(len(w["evidence"]), 2)
        self.assertEqual(w["attempts"][0]["review"]["verdict"], "pass")
        self.assertEqual(self.mcp.call_count, 3)
        self.assertEqual(server.store.load(w["id"])["status"], "awaiting_human_review")

    def test_all_decisions_persist_and_read_back(self):
        for choice, decision, status in [("Accept", "approve", "approved"), ("Partially Accept", "partial", "partially_accepted"), ("Reject", "reject", "rejected")]:
            with self.subTest(choice=choice):
                w = self.start("restaurant")
                result = self.web.post(f"/agents/workflows/{w['id']}/decision", json={"decision": choice, "reviewer": "Kevin", "notes": "Checked the evidence"})
                self.assertEqual(result.status_code, 200)
                saved = self.web.get(f"/agents/workflows/{w['id']}").get_json()
                self.assertEqual(saved["status"], status)
                self.assertEqual(saved["decisions"][-1]["decision"], decision)
                self.assertEqual(saved["decisions"][-1]["notes"], "Checked the evidence")
                self.assertEqual(server.store.load(w["id"])["decisions"], saved["decisions"])
                self.assertEqual(saved["final_response"], None if choice == "Reject" else w["attempts"][-1]["worker"]["response"])
                entries = self.web.get(f"/agents/workflows/{w['id']}/history").get_json()["history"]
                self.assertTrue(any(e["event"] == "decision" and e["actor"] == "human:Kevin" for e in entries))
                duplicate = self.web.post(f"/agents/workflows/{w['id']}/decision", json={"decision": choice, "reviewer": "Kevin", "notes": "Checked"})
                self.assertEqual(duplicate.status_code, 409)
                self.assertEqual(len(server.store.load(w["id"])["decisions"]), 1)

    def test_recent_health_and_resume(self):
        self.assertEqual(self.web.get("/agents/health").get_json()["service"], "multi-agent-server")
        w = self.start()
        self.assertEqual(self.web.get("/agents/workflows").get_json()["workflows"][0]["id"], w["id"])
        self.assertEqual(self.web.get(f"/agents/workflows/{w['id']}").get_json()["evidence"], server.store.load(w["id"])["evidence"])

    def test_name_and_single_category(self):
        result = self.web.post("/agents/workflows", json={"task": "Find this restaurant", "city": "Sydney", "category": "restaurant", "name": "  Example  "})
        self.assertEqual(result.status_code, 201)
        self.assertEqual(json.loads(result.get_json()["sources"][0]["content"])["arguments"], {"category": "restaurant", "name": "Example"})

    def test_validation_does_not_call_server(self):
        invalid = [None, [], {}, {"task": 5, "category": "all"}, {"task": " ", "category": "all"}, {"task": "x"*1001, "category": "all"}, {"task": "ok", "category": "other"}, {"task": "ok", "category": []}, {"task": "ok", "category": "all", "name": "x"*61}]
        for body in invalid:
            with self.subTest(body=body):
                self.transport.reset_mock()
                response = self.web.post("/agents/workflows", json=body)
                self.assertEqual(response.status_code, 400)
                self.transport.assert_not_called()

    def test_decision_validation_and_incomplete_workflow(self):
        w = self.start()
        path = f"/agents/workflows/{w['id']}/decision"
        for body in [{}, {"decision": "Accept", "reviewer": []}, {"decision": "Unknown", "reviewer": "K"}, {"decision": "Reject", "reviewer": "K"}, {"decision": "Partially Accept", "reviewer": "K", "notes": " "}]:
            self.assertEqual(self.web.post(path, json=body).status_code, 400)
        w["status"] = "working"; server.store.save(w)
        self.assertEqual(self.web.post(path, json={"decision": "Accept", "reviewer": "K"}).status_code, 409)

    def test_feature_boundary_and_unknown_ids(self):
        w = self.start(); w["feature"] = "student-1"; server.store.save(w)
        for suffix in ("", "/history"):
            self.assertEqual(self.web.get(f"/agents/workflows/{w['id']}" + suffix).status_code, 404)
        self.assertEqual(self.web.post(f"/agents/workflows/{w['id']}/decision", json={"decision": "Accept", "reviewer": "K"}).status_code, 404)
        self.assertEqual(self.web.get("/agents/workflows/not-an-id").status_code, 400)
        self.assertEqual(self.web.get("/agents/workflows/wf-unknown").status_code, 404)

    def test_failed_model_preserves_workflow(self):
        with patch.object(server.agents, "ask_ai_mode", side_effect=server.agents.AgentError("model offline")):
            result = self.web.post("/agents/workflows", json={"task": "Find places", "city": "Sydney", "category": "all"})
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.get_json()["workflow"]["status"], "failed")
        self.assertIsNone(result.get_json()["workflow"]["final_response"])

    def test_unavailable_evidence_stops_before_workflow(self):
        self.mcp.side_effect = mcp_client.MCPProtocolError("MCP unavailable")
        result = self.web.post("/agents/workflows", json={"task": "Find Sydney places", "city": "Sydney", "category": "all"})
        self.assertEqual(result.status_code, 502)
        self.transport.assert_not_called()

    def test_city_conflict_no_matches_and_missing_coordinates(self):
        for city, task in [("Sydney", "Plan Tokyo"), ("Unknown", "Find places")]:
            self.assertEqual(self.web.post("/agents/workflows", json={"task": task, "city": city, "category": "all"}).status_code, 400)
        self.assertTrue(place_evidence.in_city({"address": "Darlinghurst NSW", "latitude": -33.87, "longitude": 151.22}, "Sydney"))
        self.assertFalse(place_evidence.in_city({"address": "Melbourne VIC", "latitude": -33.87, "longitude": 151.22}, "Sydney"))
        self.assertTrue(place_evidence.in_city({"address": "Osaka, Japan"}, "Osaka"))
        self.assertFalse(place_evidence.in_city({"address": "Unknown"}, "Sydney"))
        self.mcp.side_effect = None; self.mcp.return_value = {"structuredContent": {"rows": []}}
        self.assertEqual(self.web.post("/agents/workflows", json={"task": "Find places", "city": "Sydney", "category": "all"}).status_code, 422)

    def test_bad_hours_and_cities_block_acceptance(self):
        for change in (lambda text: text.replace("17:00", "22:00"), lambda text: text.replace("Sydney |", "Melbourne |"), lambda text: text.replace("Sydney Opera House", "Universal Studios Japan")):
            with self.subTest(change=change):
                w = self.start(); w.pop("student2_validation", None)
                w["attempts"][-1]["worker"]["response"] = change(w["attempts"][-1]["worker"]["response"])
                server.store.save(w)
                checked = self.web.get(f"/agents/workflows/{w['id']}").get_json()
                self.assertFalse(checked["student2_validation"]["can_accept"])
                for decision in ("Accept", "Partially Accept"):
                    response = self.web.post(f"/agents/workflows/{w['id']}/decision", json={"decision": decision, "reviewer": "K", "notes": "Checked"})
                    self.assertEqual(response.status_code, 422)
                self.assertEqual(server.store.load(w["id"])["decisions"], [])

    def test_corrected_partial_response_is_validated_and_saved(self):
        w = self.start(); correct = w["attempts"][-1]["worker"]["response"]
        w["attempts"][-1]["worker"]["response"] = correct.replace("17:00", "22:00"); server.store.save(w)
        response = self.web.post(f"/agents/workflows/{w['id']}/decision", json={"decision": "Partially Accept", "reviewer": "K", "notes": "Fixed hours", "final_response": correct})
        self.assertEqual(response.status_code, 200)
        saved = server.store.load(w["id"])
        self.assertEqual(saved["final_response"], correct)
        self.assertTrue(saved["decisions"][-1]["edited_response"])
        self.assertTrue(response.get_json()["student2_final_validation"]["can_accept"])

    def test_unknown_hours_citations_and_prose_ranges(self):
        w = self.start()
        text = w["attempts"][-1]["worker"]["response"]
        self.assertTrue(place_evidence.same_hours("9:00 AM to 5:00 PM", "09:00-17:00"))
        self.assertFalse(place_evidence.same_hours("9:00 AM to 6:00 PM", "09:00-17:00"))
        self.assertFalse(place_evidence.same_hours("09:00-18:00", "See official schedule"))
        self.assertTrue(place_evidence.same_hours("Unknown", "See official schedule"))
        self.assertFalse(place_evidence.same_hours("09:00-17:00", "Weekdays 09:00-17:00"))
        for answer in (text.replace("[E1]", "[E3]"), text + "\nOpen 9:00 AM to 6:00 PM.", text + "\nIt opens at 6pm.", text.replace("stop in Sydney", "stop in Sydney at 6pm"), "A Sydney itinerary without a table."):
            self.assertFalse(place_evidence.validate(w, answer)["can_accept"])
        w["evidence"][0]["content"] = "[truncated legacy evidence"
        self.assertFalse(place_evidence.validate(w)["can_accept"])

    def test_evidence_shortlist_and_compaction(self):
        def many(category, name=None):
            return {"structuredContent": {"rows": [{"name": f"Place {n}", "category": category, "address": "Sydney NSW", "opening_hours": "09:00-17:00", "rating": n, "image_url": "x"*10000} for n in range(10)]}}
        self.mcp.side_effect = many
        sources = place_evidence.collect("Sydney", ["attraction"], "")
        self.assertEqual(len(sources), 4)
        self.assertTrue(all(len(s["content"]) < 2000 and "image_url" not in s["content"] for s in sources))
        self.assertEqual(json.loads(sources[0]["content"])["matched_count"], 10)

    def test_equivalent_table_headers_keep_strict_content_checks(self):
        w = self.start()
        answer = w["attempts"][-1]["worker"]["response"].replace("| Reason | Evidence |", "| Recommendation reason | Source |")
        self.assertTrue(place_evidence.validate(w, answer)["can_accept"])
        self.assertFalse(place_evidence.validate(w, answer.replace("09:00-17:00", "09:00-22:00"))["can_accept"])

    def test_optional_filters_are_inferred(self):
        result = self.web.post("/agents/workflows", json={"task": "Recommend Sydney sightseeing places and restaurants"})
        self.assertEqual(result.status_code, 201)
        self.assertTrue(result.get_json()["student2_validation"]["can_accept"])
        self.assertEqual(place_evidence.task_category("Melbourne activities", ""), "activity")
        self.assertEqual(place_evidence.task_category("Tokyo restaurants", ""), "restaurant")
        result = self.web.post("/agents/workflows", json={"task": "Recommend places"})
        self.assertEqual(result.status_code, 400)
        self.assertIn("optional filters", result.get_json()["error"])

    def test_combined_request_overrides_single_category(self):
        w = self.start("restaurant")
        self.assertEqual(self.mcp.call_args_list[0].args[0], "restaurant")
        self.assertEqual(self.mcp.call_args_list[1].args[0], "attraction")
        self.assertEqual(w["student2_validation"]["covered_categories"], ["attraction", "restaurant"])
        for source in w["sources"]:
            body = json.loads(source["content"])
            self.assertEqual({p["category"] for p in body["places"]}, {"attraction", "restaurant"})
            self.assertTrue(all(p["recommendation_reason"] and p["recommendation_reason"] != "Available" for p in body["places"]))

    def test_missing_category_reason_and_extra_explanation_block_accept(self):
        w = self.start()
        answer = w["attempts"][-1]["worker"]["response"]
        no_attraction = "\n".join(line for line in answer.splitlines() if "Sydney Opera House" not in line)
        available = answer.replace("Sightseeing stop in Sydney (recorded rating 4.8/5)", "Available")
        contradictory = answer + "\nOpening hours are missing but already in the table."
        for candidate in (no_attraction, available, contradictory):
            with self.subTest(candidate=candidate):
                report = place_evidence.validate(w, candidate)
                self.assertFalse(report["can_accept"], report)
        self.assertIn("required categories", " ".join(place_evidence.validate(w, no_attraction)["issues"]))
        self.assertIn("recommendation reason", " ".join(place_evidence.validate(w, available)["issues"]))

    def test_real_place_description_is_the_recommendation_reason(self):
        row = {"name": "Gallery", "category": "attraction", "description": "Public art museum beside the harbour", "rating": 4.7}
        reason = place_evidence.recommendation(row, "Sydney")
        self.assertIn(row["description"], reason)
        self.assertIn("Sightseeing", reason)
        self.assertIn("4.7/5", reason)
        self.assertNotIn("Available", reason)

    def test_required_category_absent_stops_workflow(self):
        original = self.mcp.side_effect
        self.mcp.side_effect = lambda category, name=None: {"structuredContent": {"rows": []}} if category == "attraction" else original(category, name)
        result = self.web.post("/agents/workflows", json={"task": "Plan Sydney attractions and dining", "city": "Sydney", "category": "restaurant"})
        self.assertEqual(result.status_code, 422)
        self.assertIn("attraction", result.get_json()["error"])
        self.transport.assert_not_called()

    def test_transport_errors_and_disabled(self):
        for exc, code in [(requests.Timeout(), 504), (requests.ConnectionError(), 503)]:
            with self.subTest(code=code):
                self.transport.side_effect = exc
                response = self.web.get("/agents/health")
                self.assertEqual(response.status_code, code)
        with patch.dict(os.environ, {"MULTI_AGENT_ENABLED": "false"}):
            self.transport.reset_mock()
            self.assertEqual(self.web.get("/agents/health").status_code, 503)
            self.transport.assert_not_called()

    def test_invalid_shared_responses(self):
        self.transport.side_effect = None
        for value in ([], None):
            self.transport.return_value = Mock(status_code=200, json=lambda: value)
            self.assertEqual(self.web.get("/agents/health").status_code, 502)
        self.transport.return_value = Mock(status_code=200)
        self.transport.return_value.json.side_effect = ValueError("not json")
        self.assertEqual(self.web.get("/agents/health").status_code, 502)
        self.transport.return_value = Mock(status_code=200, json=lambda: {"feature": "student-2", "id": "bad", "status": "working"})
        self.assertEqual(self.web.get("/agents/workflows/wf-test").status_code, 502)

    def test_existing_routes_remain_registered(self):
        rules = {r.rule for r in app.url_map.iter_rules()}
        self.assertTrue({"/places", "/favourites", "/ai/recommend", "/mcp/search-places", "/rag/search", "/rag/ask", "/rag/reindex"} <= rules)
        # This checks enabled-route input validation, independent of CI's disabled flags.
        with patch.dict(os.environ, {"MCP_ENABLED": "true", "RAG_ENABLED": "true"}):
            self.assertEqual(self.web.post("/mcp/search-places", json={}).status_code, 400)
            self.assertEqual(self.web.post("/rag/search", json={"query": " "}).status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
