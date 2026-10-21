"""Backend fragments poll long cloud jobs using the existing frontend HTMX."""
import importlib.util
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load_view(student):
    filename = "agents.py" if student == 1 else "agent_formatter.py"
    path = ROOT / f"student-{student}" / "api" / "views" / filename
    spec = importlib.util.spec_from_file_location(f"cloud_polling_view_{student}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowElement(HTMLParser):
    def __init__(self, fragment):
        super().__init__()
        self.workflow = None
        self.feed(fragment)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "data-workflow-id" in values:
            self.workflow = values


class AgentPollingTests(unittest.TestCase):
    def render(self, student, status):
        view = load_view(student)
        workflow = {
            "id": "wf-test-polling", "feature": f"student-{student}",
            "task": "Read the supplied evidence.", "round": 1,
            "status": status, "plan": None, "evidence": [],
            "attempts": [], "decisions": [], "final_response": None,
        }
        fragment = view.workflow_card(workflow)
        return WorkflowElement(fragment).workflow, fragment

    def test_pending_jobs_poll_the_same_application_workflow(self):
        for student in (1, 3):
            for status in ("planning", "gathering_evidence", "working", "reviewing"):
                with self.subTest(student=student, status=status):
                    attrs, fragment = self.render(student, status)
                    path = "ai/agents" if student == 1 else "ai/multi-agent"
                    self.assertEqual(attrs["hx-get"], f"/api/student-{student}/{path}/wf-test-polling")
                    self.assertEqual(attrs["hx-trigger"], "every 2s")
                    self.assertEqual(attrs["hx-target"], "this")
                    self.assertEqual(attrs["hx-swap"], "outerHTML")
                    self.assertEqual(attrs["data-workflow-status"], status)
                    self.assertEqual(attrs["data-workflow-feature"], f"student-{student}")
                    self.assertNotIn("<form", fragment)

    def test_human_review_stops_polling_and_keeps_the_decision_form(self):
        for student in (1, 3):
            with self.subTest(student=student):
                attrs, fragment = self.render(student, "awaiting_human_review")
                self.assertNotIn("hx-trigger", attrs)
                self.assertNotIn("hx-get", attrs)
                self.assertIn("<form", fragment)
                self.assertIn("/decision", fragment)

    def test_finished_and_failed_jobs_do_not_keep_polling(self):
        for student in (1, 3):
            for status in ("approved", "partially_accepted", "rejected", "failed"):
                with self.subTest(student=student, status=status):
                    attrs, fragment = self.render(student, status)
                    self.assertNotIn("hx-trigger", attrs)
                    self.assertNotIn("hx-get", attrs)
                    self.assertNotIn("<form", fragment)


if __name__ == "__main__":
    unittest.main(verbosity=2)
