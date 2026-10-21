"""Cloud verification reads the students' existing workflow HTML unchanged."""

import copy
import importlib.util
from html.parser import HTMLParser
from pathlib import Path
import unittest

from check_cloud_ai import CheckFailed
from test_cloud_ai import FakeTransport, checks, response, workflow

ROOT = Path(__file__).resolve().parents[2]
PATHS = {1: "/api/student-1/ai/agents", 3: "/api/student-3/ai/multi-agent"}


def load_view(student):
    filename = "agents.py" if student == 1 else "agent_formatter.py"
    path = ROOT / f"student-{student}" / "api" / "views" / filename
    spec = importlib.util.spec_from_file_location(f"cloud_existing_agent_view_{student}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Elements(HTMLParser):
    def __init__(self, fragment):
        super().__init__()
        self.nodes = []
        self.feed(fragment)

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def example(student, status):
    result = workflow()
    result.update(feature=f"student-{student}", status=status, round=1,
                  created_at="2026-10-21T12:00:00+00:00", decisions=[])
    # Existing views render partial work before a Worker attempt exists.
    if status in ("queued", "planning", "gathering_evidence", "working", "reviewing"):
        result.update(plan=None, evidence=[], attempts=[])
    else:
        result["plan"].update(goal="Read the place evidence.", required_evidence=["S1"])
        result["evidence"][0].update(label="Place data", content="Sydney harbour.", kind="supplied")
        result["attempts"][0].update(round=1)
        review = result["attempts"][0]["review"]
        review.update(risks=[], recommendations=[])
    return result


class ExistingAgentViewTests(unittest.TestCase):
    def render(self, student, status):
        sample = example(student, status)
        return sample, load_view(student).workflow_card(sample)

    def test_existing_html_exposes_each_pending_and_human_review_state(self):
        statuses = ("queued", "planning", "gathering_evidence", "working", "reviewing",
                    "awaiting_human_review", "rejected")
        for student in (1, 3):
            for status in statuses:
                with self.subTest(student=student, status=status):
                    sample, fragment = self.render(student, status)
                    transport = FakeTransport(run=copy.deepcopy(sample))
                    verifier = checks(transport)
                    self.assertEqual(verifier.application_workflow(
                        response(fragment), student, sample["id"]), status)
                    self.assertIn(sample["id"], fragment)
                    self.assertIn(f"Validation reference {verifier.marker}.", fragment)

    def test_unchanged_cards_do_not_require_status_metadata_or_automatic_polling(self):
        for student in (1, 3):
            for status in ("planning", "reviewing", "awaiting_human_review", "rejected"):
                with self.subTest(student=student, status=status):
                    _, fragment = self.render(student, status)
                    attrs = Elements(fragment).nodes[0][1]
                    self.assertNotIn("data-workflow-id", attrs)
                    self.assertNotIn("data-workflow-status", attrs)
                    self.assertNotIn("data-workflow-feature", attrs)
                    self.assertNotIn("hx-get", attrs)
                    self.assertNotIn("hx-trigger", attrs)
                    self.assertNotIn("every 2s", fragment)

    def test_existing_human_review_form_and_final_state_are_preserved(self):
        for student in (1, 3):
            with self.subTest(student=student):
                sample, fragment = self.render(student, "awaiting_human_review")
                forms = [attrs for tag, attrs in Elements(fragment).nodes if tag == "form"]
                self.assertEqual(len(forms), 1)
                self.assertEqual(forms[0]["hx-post"], f"{PATHS[student]}/{sample['id']}/decision")
                self.assertIn('name="reviewer"' if student == 3 else "name='reviewer'", fragment)
                self.assertNotIn("<form", self.render(student, "rejected")[1])

    def test_existing_recent_list_can_open_a_pending_workflow_manually(self):
        for student in (1, 3):
            with self.subTest(student=student):
                sample = example(student, "reviewing")
                sample.update(verdict=None, updated_at=sample["created_at"])
                fragment = load_view(student).workflow_list([sample])
                buttons = [attrs for tag, attrs in Elements(fragment).nodes if tag == "button"]
                self.assertEqual(len(buttons), 1)
                self.assertEqual(buttons[0]["hx-get"], f"{PATHS[student]}/{sample['id']}")
                self.assertEqual(buttons[0]["hx-swap"], "innerHTML")
                self.assertIn("Open", fragment)

    def test_existing_rendered_card_cannot_substitute_another_workflow_or_task(self):
        for student in (1, 3):
            for mutation in ({"id": "wf-another-run"}, {"task": "A different validation task."}):
                with self.subTest(student=student, mutation=mutation):
                    sample = example(student, "reviewing")
                    substituted = copy.deepcopy(sample)
                    substituted.update(mutation)
                    fragment = load_view(student).workflow_card(substituted)
                    verifier = checks(FakeTransport(run=sample))
                    with self.assertRaises(CheckFailed):
                        verifier.application_workflow(response(fragment), student, sample["id"])

    def test_existing_task_text_stays_escaped_and_verifiable(self):
        for student in (1, 3):
            with self.subTest(student=student):
                sample = example(student, "planning")
                sample["task"] = 'Check <script>alert("model")</script>. Validation reference test-run.'
                fragment = load_view(student).workflow_card(sample)
                self.assertNotIn("<script>", fragment)
                self.assertIn("&lt;script&gt;", fragment)
                verifier = checks(FakeTransport(run=copy.deepcopy(sample)))
                self.assertEqual(verifier.application_workflow(
                    response(fragment), student, sample["id"]), "planning")


if __name__ == "__main__":
    unittest.main(verbosity=2)
