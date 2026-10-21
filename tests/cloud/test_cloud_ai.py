"""Offline failure-path tests for the live verifier; no cloud requests or LLM."""

import copy
import html
import json
import unittest
from unittest.mock import patch

from check_cloud_ai import (
    CheckFailed, CloudChecks, Response, assignments, body, validate_mcp,
    main, validate_numbered_citations, validate_price_range_fact, validate_rag, validate_workflow,
)


MODEL = "test-model"


def response(value, status=200):
    return Response(status, json.dumps(value) if not isinstance(value, str) else value)


def workflow(marker="test-run"):
    return {
        "id": "wf-test-123", "task": f"Recommend a place. Validation reference {marker}.", "feature": "student-2",
        "status": "awaiting_human_review", "error": None, "final_response": None,
        "plan": {"source": "model", "model": MODEL, "steps": ["read evidence"],
                 "acceptance_criteria": ["cite evidence"]},
        "evidence": [{"id": "E1", "ok": True}],
        "attempts": [{"worker": {"model": MODEL, "response": "Visit the harbour [E1]."},
                      "review": {"source": "model", "model": MODEL, "verdict": "pass",
                                 "criteria": [{"criterion": "Cites usable evidence", "met": True}]}}],
    }


class FakeTransport:
    """Exercises the same API sequence without opening a socket."""
    def __init__(self, run=None):
        self.run = run or workflow()
        self.calls = []
        self.app_response = None

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/decision"):
            self.run["status"] = "rejected"
            return response(self.run)
        if url.endswith("/history"):
            return response({"history": [{"actor": a, "event": e} for a, e in
                            (("planner", "plan"), ("worker", "response"), ("reviewer", "review"))]})
        if url.endswith("/agents/workflows") and method == "POST":
            return self.app_response or response(self.run, 201)
        if url.endswith("/workflows/wf-test-123"):
            return response(self.run)
        if url.endswith("/model"):
            return response({"reachable": True, "model": MODEL})
        if url.endswith("/health"):
            service = {"ai": "ai-mode", "mcp": "mcp-server", "rag": "rag-server",
                       "agents": "multi-agent-server"}[url.split("/")[-2]]
            return response({"service": service, "status": "running"})
        if self.app_response is not None:
            return self.app_response
        raise AssertionError(f"Unexpected request: {method} {url}")


def checks(transport, **options):
    result = CloudChecks(transport, {n: f"http://frontend-{n}/api/student-{n}" for n in range(1, 6)},
                         "http://shared/ai", "http://shared/mcp", "http://shared/rag", "http://shared/agents",
                         **options)
    result.model, result.marker = MODEL, "test-run"
    return result


class FakeClock:
    def __init__(self):
        self.now = 0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class AsyncTransport(FakeTransport):
    """Queued work completes only after reads through the application proxy."""
    def __init__(self, student=2, states=None):
        super().__init__()
        self.student = student
        self.run["feature"] = f"student-{student}"
        self.run["status"] = "queued"
        self.states = list(states if states is not None else ["planning", "reviewing", "awaiting_human_review"])
        self.path = {1: "/ai/agents", 2: "/agents/workflows", 3: "/ai/multi-agent"}[student]
        self.app_base = f"http://frontend-{student}/api/student-{student}"
        self.read_failure = None
        self.read_patch = {}
        self.decision_failure = None
        self.history = [{"actor": a, "event": e} for a, e in
                        (("planner", "plan"), ("worker", "response"), ("reviewer", "review"))]

    def rendered(self, status=200):
        snapshot = copy.deepcopy(self.run)
        snapshot.update(self.read_patch)
        if snapshot["status"] in ("queued", "planning", "working", "reviewing"):
            snapshot["attempts"] = []
        if self.student == 2:
            return response(snapshot, status)
        wid, state, task = (html.escape(snapshot[key], quote=True) for key in ("id", "status", "task"))
        if self.student == 1:
            label = "awaiting your review" if state == "awaiting_human_review" else state.replace("_", " ")
            return response(
                '<article class="agent-run"><header class="agent-run__head">'
                f'<div><strong>{task}</strong><p class="muted"><code>{wid}</code> &middot; round 1</p></div>'
                f'<span class="pill pill-planned">{label}</span></header></article>', status)
        return response(
            f'<div class="card agent-card" id="{wid}"><p><strong>Workflow</strong> <code>{wid}</code> '
            f'<span class="pill pill-{state}">{state}</span> <span class="muted">round 1</span></p>'
            f'<p class="muted">Task: {task}</p></div>', status)

    def request(self, method, url, **kwargs):
        if method == "POST" and url == self.app_base + self.path:
            self.calls.append((method, url, kwargs))
            return self.rendered(202 if self.student == 2 else 200)
        if method == "GET" and url == self.app_base + self.path + "/wf-test-123":
            self.calls.append((method, url, kwargs))
            if self.read_failure is not None:
                return self.read_failure
            if self.states:
                self.run["status"] = self.states.pop(0)
            return self.rendered()
        if url.endswith("/history"):
            self.calls.append((method, url, kwargs))
            return response({"history": self.history})
        if url == self.app_base + self.path + "/wf-test-123/decision":
            self.calls.append((method, url, kwargs))
            if self.decision_failure is not None:
                return self.decision_failure
            self.run["status"] = "rejected"
            return self.rendered()
        return super().request(method, url, **kwargs)


class AsyncCloudVerifierTests(unittest.TestCase):
    def configured(self, transport, *, timeout=900, interval=2):
        clock = FakeClock()
        return checks(transport, workflow_timeout=timeout, poll_interval=interval,
                      clock=clock.monotonic, sleep=clock.sleep), clock

    def test_slow_queued_work_is_polled_through_each_application_then_audited_and_rejected(self):
        for student in (1, 2, 3):
            with self.subTest(student=student):
                transport = AsyncTransport(student, ["planning", "working", "reviewing", "awaiting_human_review"])
                verifier, clock = self.configured(transport, interval=125)
                verifier.b4(student)
                self.assertEqual(clock.now, 500)
                app_reads = [c for c in transport.calls if c[0] == "GET" and c[1].startswith(transport.app_base)]
                self.assertEqual(len(app_reads), 4)
                self.assertTrue(all(c[1].endswith(transport.path + "/wf-test-123") for c in app_reads))
                self.assertEqual(transport.run["status"], "rejected")
                self.assertIsNone(transport.run["final_response"])
                self.assertTrue(any(c[1].endswith("/history") for c in transport.calls))
                decision = [c for c in transport.calls if c[1].endswith("/decision")]
                self.assertEqual(len(decision), 1)
                self.assertEqual(decision[0][2]["payload" if student == 2 else "form"]["decision"],
                                 "Reject" if student == 2 else "reject")

    def test_queued_forever_fails_at_deadline_without_releasing_or_deciding_it(self):
        transport = AsyncTransport(states=[])
        verifier, clock = self.configured(transport, timeout=5)
        with self.assertRaisesRegex(CheckFailed, "5s deadline.*queued"):
            verifier.b4(2)
        self.assertEqual(clock.now, 5)
        self.assertEqual(transport.run["status"], "queued")
        self.assertFalse(any(c[1].endswith(("/history", "/decision")) for c in transport.calls))

    def test_terminal_failed_work_does_not_count_as_a_completed_run(self):
        transport = AsyncTransport(states=["failed"])
        verifier, _ = self.configured(transport)
        with self.assertRaises(CheckFailed):
            verifier.b4(2)
        self.assertEqual(transport.run["status"], "failed")
        self.assertFalse(any(c[1].endswith(("/history", "/decision")) for c in transport.calls))

    def test_broken_application_read_is_not_bypassed_using_the_shared_server(self):
        for student in (1, 2, 3):
            with self.subTest(student=student):
                transport = AsyncTransport(student)
                transport.read_failure = response({"error": "proxy failed"}, 503)
                verifier, _ = self.configured(transport)
                with self.assertRaisesRegex(CheckFailed, "HTTP 503"):
                    verifier.b4(student)
                self.assertFalse(any(c[1].endswith("/history") for c in transport.calls))

    def test_html_error_notice_cannot_pass_as_status_or_success(self):
        for student in (1, 3):
            for css in ("notice-error", "error"):
                with self.subTest(student=student, css=css):
                    transport = AsyncTransport(student)
                    transport.read_failure = response(f'<div class="{css}">Upstream failed.</div>')
                    verifier, _ = self.configured(transport)
                    with self.assertRaisesRegex(CheckFailed, "rendered an error"):
                        verifier.b4(student)

    def test_poll_response_cannot_switch_workflow_feature_id_or_validation_run(self):
        for student in (1, 2, 3):
            for patch_ in ({"feature": "student-5"}, {"id": "wf-another-run"},
                           {"task": "Validation reference someone-else."}):
                with self.subTest(student=student, patch=patch_):
                    transport = AsyncTransport(student)
                    # Apply tampering only after the valid initial response.
                    original = transport.request
                    def request(method, url, **kwargs):
                        if method == "GET" and url.startswith(transport.app_base):
                            if "feature" in patch_:
                                # Original HTML has no feature field, so the
                                # shared JSON ownership check must catch it.
                                transport.run.update(patch_)
                            else:
                                transport.read_patch = patch_
                        return original(method, url, **kwargs)
                    transport.request = request
                    verifier, _ = self.configured(transport)
                    with self.assertRaises(CheckFailed):
                        verifier.b4(student)
                    self.assertFalse(any(c[1].endswith("/decision") for c in transport.calls))

    def test_initial_shared_ownership_is_checked_before_application_polling(self):
        for student in (1, 2, 3):
            for patch_ in ({"feature": "student-5"},
                           {"task": "Validation reference someone-else."}):
                with self.subTest(student=student, patch=patch_):
                    transport = AsyncTransport(student)
                    transport.run.update(patch_)
                    verifier, _ = self.configured(transport)
                    with self.assertRaisesRegex(CheckFailed, "does not belong"):
                        verifier.b4(student)
                    app_reads = [c for c in transport.calls if c[0] == "GET"
                                 and c[1].startswith(transport.app_base)]
                    self.assertEqual(app_reads, [])
                    self.assertFalse(any(c[1].endswith("/decision") for c in transport.calls))

    def test_original_html_requires_header_id_task_and_unambiguous_known_status(self):
        for student in (1, 3):
            transport = AsyncTransport(student)
            verifier, _ = self.configured(transport)
            source = transport.rendered().text
            malformed = [source.replace("<code>wf-test-123</code>", "<code>wf-other</code>"),
                         source.replace("Validation reference test-run.", "Validation reference another-run."),
                         source.replace("queued", "unexpected-status")]
            # Duplicate status inside the header must fail; another pill in a
            # later evidence or reviewer block must not change the status.
            duplicated = (source.replace("</header>", "<span class='pill'>queued</span></header>")
                          if student == 1 else source.replace("</p>", "<span class='pill'>queued</span></p>", 1))
            malformed.append(duplicated)
            for text in malformed:
                with self.subTest(student=student, text=text), self.assertRaises(CheckFailed):
                    verifier.application_workflow(response(text), student, "wf-test-123")

    def test_later_evidence_and_reviewer_pills_do_not_masquerade_as_workflow_status(self):
        for student in (1, 3):
            transport = AsyncTransport(student)
            verifier, _ = self.configured(transport)
            source = transport.rendered().text
            tail = '<section><span class="pill pill-booked">fetched</span><span class="pill">pass</span></section>'
            close = "</article>" if student == 1 else "</div>"
            source = source.rsplit(close, 1)[0] + tail + close
            with self.subTest(student=student):
                self.assertEqual(verifier.application_workflow(response(source), student, "wf-test-123"), "queued")

    def test_app_completion_still_requires_real_model_and_all_three_audit_events(self):
        for fault in ("model", "audit"):
            with self.subTest(fault=fault):
                transport = AsyncTransport(states=["awaiting_human_review"])
                if fault == "model":
                    transport.run["attempts"][0]["review"]["source"] = "fallback"
                else:
                    transport.history = transport.history[:-1]
                verifier, _ = self.configured(transport)
                with self.assertRaises(CheckFailed):
                    verifier.b4(2)
                self.assertEqual(transport.run["status"], "rejected")

    def test_app_must_confirm_rejection_after_model_and_audit_checks(self):
        transport = AsyncTransport(states=["awaiting_human_review"])
        transport.decision_failure = response({"error": "decision was not recorded"})
        verifier, _ = self.configured(transport)
        with self.assertRaises(CheckFailed):
            verifier.b4(2)
        self.assertEqual(transport.run["status"], "awaiting_human_review")
        self.assertTrue(any(c[1].endswith("/history") for c in transport.calls))

    def test_pending_and_already_released_work_cannot_pass_validation(self):
        for status in ("planning", "reviewing", "approved", "partially_accepted", "rejected"):
            transport = AsyncTransport(states=[status])
            verifier, _ = self.configured(transport, timeout=5)
            with self.subTest(status=status), self.assertRaises(CheckFailed):
                verifier.b4(2)
            self.assertFalse(any(c[1].endswith("/history") for c in transport.calls))

    def test_cli_rejects_unbounded_or_nonpositive_workflow_waiting_options(self):
        for option in ("--workflow-timeout", "--poll-interval"):
            for value in ("0", "-1", "nan", "inf"):
                with self.subTest(option=option, value=value), patch("sys.stderr"), self.assertRaises(SystemExit):
                    main([option, value])


class CloudVerifierTests(unittest.TestCase):
    def test_503_and_disabled_200_are_failures(self):
        for result in (response({"error": "generation failed"}, 503),
                       response({"disabled": True}), response({"status": "disabled"}),
                       response({"status": "unavailable"}), response({"error": "upstream failed"})):
            with self.subTest(result=result), self.assertRaises(CheckFailed):
                body(result)

    def test_ai_html_error_or_empty_answer_cannot_pass(self):
        transport = FakeTransport()
        for text in ("<div class='notice notice-error'>AI is disabled</div>",
                     "<p>AI-Mode could not answer that.</p>",
                     "<div class='chat-msg bot'>NextStop AI</div>"):
            transport.app_response = response(text)
            with self.subTest(text=text), self.assertRaises(CheckFailed):
                checks(transport).b1()

    def test_ai_generated_answer_passes_through_existing_frontend_proxy(self):
        transport = FakeTransport()
        transport.app_response = response("<div class='chat-msg bot'><div>NextStop AI</div>"
                                          "<div class='bubble'>Reserve travel time between activities.</div></div>")
        checks(transport).b1()
        self.assertEqual(transport.calls[0][1], "http://frontend-1/api/student-1/ai/chat")
        self.assertIn("form", transport.calls[0][2])

    def test_mcp_requires_real_rows_from_correct_feature(self):
        valid = {"structuredContent": {"source": "student-2-db", "rows": [{"name": "Harbour"}], "row_count": 1}}
        self.assertEqual(validate_mcp(valid, 2), [{"name": "Harbour"}])
        for bad in ({"isError": True, **valid},
                    {"source": "student-5-db", "rows": [{"name": "Harbour"}], "row_count": 1},
                    {"source": "student-2-db", "rows": [], "row_count": 0},
                    {"source": "student-2-db", "rows": [{"name": "Harbour"}], "row_count": 0}):
            with self.subTest(result=bad), self.assertRaises(CheckFailed):
                validate_mcp(bad, 2)

    def test_rag_insufficient_context_missing_model_or_citations_cannot_pass(self):
        valid = {"grounded": True, "confidence": "high", "answer": "Visit Sydney Harbour [1].",
                 "model": MODEL, "citations": [{"source": "travel.md", "excerpt": "Sydney Harbour", "number": 1}]}
        validate_rag(valid, MODEL)
        for patch in ({"grounded": False}, {"model": None}, {"model": "different-model"},
                      {"citations": []}, {"confidence": "insufficient"},
                      {"answer": "A plausible response without source references."}, {"answer": ""}):
            with self.subTest(patch=patch), self.assertRaises(CheckFailed):
                validate_rag({**valid, **patch}, MODEL)

    def test_grouped_citations_are_valid_only_when_all_numbers_are_retrieved(self):
        validate_numbered_citations("Plan one activity per day [1, 2].", {1, 2})
        validate_numbered_citations("Plan breaks [1], then allow travel time [2].", {1, 2})
        for answer in ("No citation supplied.", "A tip [99].", "A tip [1, 99].",
                       "A tip [1], with extra unsupported detail [99].",
                       "A tip [1], and a range [1-99]."):
            with self.subTest(answer=answer), self.assertRaisesRegex(CheckFailed, "allowed=.*cited=.*answer="):
                validate_numbered_citations(answer, {1, 2})

    def test_worker_citation_error_reports_available_and_actual_ids(self):
        bad = workflow()
        bad["attempts"][0]["worker"]["response"] = "Invented detail [E99]."
        with self.assertRaisesRegex(CheckFailed, "usable=.*E1.*cited=.*E99.*answer="):
            validate_workflow(bad, 2, MODEL)

    def test_price_range_grounding_rejects_wrong_price_and_not_free(self):
        validate_price_range_fact("A price_range value of 0 means that general entry is free. [1]")
        for answer in ("A price_range value of 0 means general entry is A$50. [1]",
                       "A value of 0 means general entry is not free. [1]",
                       "Zero does not mean free general entry. [1]",
                       "A value of 0 means entry is free, but tickets cost A$50. [1]"):
            with self.subTest(answer=answer), self.assertRaises(CheckFailed):
                validate_price_range_fact(answer)

    def test_workflow_fallback_does_not_count_as_live_agents(self):
        validate_workflow(workflow(), 2, MODEL)
        for agent in ("planner", "reviewer", "worker"):
            bad = workflow()
            if agent == "planner":
                bad["plan"]["source"] = "fallback"
            elif agent == "reviewer":
                bad["attempts"][0]["review"]["source"] = "fallback"
            else:
                bad["attempts"][0]["worker"]["model"] = None
            with self.subTest(agent=agent), self.assertRaises(CheckFailed):
                validate_workflow(bad, 2, MODEL)

    def test_workflow_uncited_or_unavailable_evidence_cannot_pass(self):
        for answer in ("A reply without citations", "Invented detail [E99]."):
            bad = workflow()
            bad["attempts"][0]["worker"]["response"] = answer
            with self.subTest(answer=answer), self.assertRaises(CheckFailed):
                validate_workflow(bad, 2, MODEL)

    def test_critical_model_review_is_completed_and_test_output_is_rejected(self):
        transport = FakeTransport()
        review = transport.run["attempts"][0]["review"]
        review.update(verdict="fail", criteria=[{"criterion": "States the trip ID", "met": False,
                                               "note": "The response omitted the trip ID."}])
        checks(transport).b4(2)
        self.assertEqual(transport.run["status"], "rejected")
        self.assertIsNone(transport.run["final_response"])

    def test_unknown_verdict_missing_or_empty_criteria_are_not_a_completed_review(self):
        for patch in ({"verdict": "unknown"}, {"verdict": None}, {"criteria": None},
                      {"criteria": []}, {"criteria": [{}]},
                      {"criteria": [{"criterion": "Has a citation", "met": "false"}]},
                      {"criteria": [{"criterion": "", "met": True}]}):
            bad = workflow()
            bad["attempts"][0]["review"].update(patch)
            with self.subTest(patch=patch), self.assertRaises(CheckFailed):
                validate_workflow(bad, 2, MODEL)

    def test_html_rag_requires_generated_answer_and_actual_citation(self):
        class RagTransport(FakeTransport):
            def request(self, method, url, **kwargs):
                if url.endswith("/search"):
                    return response({"confidence": "high", "hits": [
                        {"source": "travel.md", "number": 1},
                        {"source": "safety.md", "number": 2}]})
                return self.app_response
        transport = RagTransport()
        for student in (1, 3):
            if student == 1:
                template = ("<div class='chat-msg user'><div class='bubble'>Question</div></div>"
                            "<div class='chat-msg bot'><div class='bubble'>%s"
                            "<div class='citations'><ol class='citation-list'><li>travel.md</li></ol>"
                            "</div></div></div>")
            else:
                template = ("<div class='card'><p><strong>Grounded answer</strong></p>"
                            "<p>%s</p><ol class='citation-list'><li>travel.md</li></ol></div>")
            transport.app_response = response(template % "Plan one activity per day [1].")
            checks(transport).b3(student)
            transport.app_response = response(template % "Plan one activity per day [1, 2].")
            checks(transport).b3(student)
            for answer in ("", "A plausible answer without citations.", "Something fabricated [99].",
                           "An otherwise cited answer [1] with an invented source [99]."):
                transport.app_response = response(template % answer)
                with self.subTest(student=student, answer=answer), self.assertRaises(CheckFailed):
                    checks(transport).b3(student)

    def test_workflow_closes_test_record_without_releasing_answer(self):
        transport = FakeTransport()
        checks(transport).b4(2)
        self.assertEqual(transport.run["status"], "rejected")
        self.assertIsNone(transport.run["final_response"])
        decisions = [c for c in transport.calls if c[1].endswith("/decision")]
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0][2]["payload"]["decision"], "Reject")

    def test_failed_validation_still_closes_own_completed_workflow(self):
        transport = FakeTransport()
        transport.run["plan"]["source"] = "fallback"
        with self.assertRaises(CheckFailed):
            checks(transport).b4(2)
        self.assertEqual(transport.run["status"], "rejected")

    def test_never_closes_a_workflow_from_another_run(self):
        transport = FakeTransport(workflow("someone-elses-run"))
        before = copy.deepcopy(transport.run)
        with self.assertRaises(CheckFailed):
            checks(transport).b4(2)
        self.assertEqual(transport.run, before)
        self.assertFalse(any(c[1].endswith("/decision") for c in transport.calls))

    def test_failed_workflow_is_preserved_without_an_illegal_decision(self):
        transport = FakeTransport()
        transport.run.update(status="failed", error="Model failed during generation")
        checks(transport).close_workflow("wf-test-123", 2, "/agents/workflows")
        self.assertFalse(any(c[1].endswith("/decision") for c in transport.calls))

    def test_initial_timeout_still_fails_and_recovers_only_its_own_completed_record(self):
        class TimeoutTransport(FakeTransport):
            def request(self, method, url, **kwargs):
                if method == "POST" and url.endswith("/agents/workflows"):
                    self.calls.append((method, url, kwargs))
                    raise CheckFailed("Initial application request timed out")
                if "workflows?" in url:
                    self.calls.append((method, url, kwargs))
                    other_marker = {**self.run, "id": "wf-other-run", "task": "Validation reference test-run-other."}
                    other_feature = {**self.run, "id": "wf-other-feature", "feature": "student-1"}
                    return response({"workflows": [other_marker, other_feature, self.run]})
                return super().request(method, url, **kwargs)
        transport = TimeoutTransport()
        with self.assertRaisesRegex(CheckFailed, "Initial application request timed out"):
            checks(transport).b4(2)
        self.assertEqual(transport.run["status"], "rejected")
        lookups = [c for c in transport.calls if "workflows?" in c[1]]
        self.assertEqual(len(lookups), 1)
        self.assertFalse(any("wf-other" in c[1] for c in transport.calls))

    def test_initial_timeout_reports_pending_record_without_deciding_it(self):
        class PendingTransport(FakeTransport):
            def request(self, method, url, **kwargs):
                if method == "POST" and url.endswith("/agents/workflows"):
                    raise CheckFailed("Initial application request timed out")
                if "workflows?" in url:
                    self.calls.append((method, url, kwargs))
                    return response({"workflows": [self.run]})
                return super().request(method, url, **kwargs)
        transport = PendingTransport()
        transport.run["status"] = "working"
        with self.assertRaisesRegex(CheckFailed, "Initial application request timed out"):
            checks(transport).b4(2)
        self.assertEqual(transport.run["status"], "working")
        self.assertFalse(any(c[1].endswith("/decision") for c in transport.calls))

    def test_ready_requires_a_live_model_not_only_health(self):
        class UnreachableModel(FakeTransport):
            def request(self, method, url, **kwargs):
                if url.endswith("/model"):
                    return response({"reachable": False, "model": MODEL})
                return super().request(method, url, **kwargs)
        with self.assertRaises(CheckFailed):
            checks(UnreachableModel()).readiness()

    def test_url_overrides_preserve_proxy_prefix(self):
        self.assertEqual(assignments(["2=http://localhost:8080/api/student-2/"]),
                         {2: "http://localhost:8080/api/student-2"})


if __name__ == "__main__":
    unittest.main()
