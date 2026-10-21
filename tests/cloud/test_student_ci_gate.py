"""Keep automatic deployments behind the push checks selected for that commit."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "student_ci_gate", ROOT / "deploy/azure/wait_for_student_ci.py",
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)

SHA = "a" * 40
BEFORE = "b" * 40
WORKFLOW = "student-2.yml"


def run(identifier=1, *, status="completed", conclusion="success", **fields):
    return {
        "id": identifier, "status": status, "conclusion": conclusion,
        "head_sha": SHA, "head_branch": "main", "event": "push", **fields,
    }


class Clock:
    def __init__(self):
        self.elapsed = 0
        self.sleeps = []

    def now(self):
        return self.elapsed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds


class GithubFixture:
    def __init__(self, snapshots=(), main=(SHA,)):
        self.snapshots = list(snapshots)
        self.main = list(main)
        self.run_calls = []

    def latest_main(self):
        value = self.main.pop(0) if len(self.main) > 1 else self.main[0]
        if isinstance(value, Exception):
            raise value
        return value

    def workflow_runs(self, workflow, sha):
        self.run_calls.append((workflow, sha))
        value = self.snapshots.pop(0) if len(self.snapshots) > 1 else self.snapshots[0]
        if isinstance(value, Exception):
            raise value
        return value


class ExpectedStudentChecksTests(unittest.TestCase):
    def test_student_changes_wait_for_only_the_affected_student(self):
        self.assertEqual(gate.expected_workflows(["student-2/api/routes/places.py"]), {WORKFLOW})
        self.assertEqual(gate.expected_workflows(["student-1/deleted.py", "student-3/moved.py"]),
                         {"student-1.yml", "student-3.yml"})

    def test_shared_runtime_and_shared_compose_changes_require_all_students(self):
        expected = {f"student-{number}.yml" for number in range(1, 6)}
        for changed in ("shared/auth.py", "ai-services/rag-server/server.py", "scripts/smoke_test.py",
                        "docker-compose.yml"):
            with self.subTest(path=changed):
                self.assertEqual(gate.expected_workflows([changed]), expected)

    def test_student_workflow_change_requires_that_workflow(self):
        self.assertEqual(gate.expected_workflows([".github/workflows/student-4.yml"]),
                         {"student-4.yml"})

    def test_deployment_only_and_unrelated_paths_do_not_wait_for_nonexistent_checks(self):
        self.assertEqual(gate.expected_workflows([
            "deploy/azure/configure_ai.sh", "docker-compose.cloud.yml", "tests/cloud/test_deployment.py",
            ".github/workflows/cloud-deployment.yml", "README.md", "student-20/api.py",
        ]), set())

    def test_expectations_match_the_existing_student_push_path_filters(self):
        self.assertEqual(set(gate.WORKFLOW_PATHS),
                         {f"student-{number}.yml" for number in range(1, 6)})
        for filename, expected in gate.WORKFLOW_PATHS.items():
            lines = (ROOT / ".github/workflows" / filename).read_text().splitlines()
            push = lines.index("  push:")
            end = next(index for index in range(push + 1, len(lines))
                       if lines[index].startswith("  ") and not lines[index].startswith("   ")
                       and lines[index].strip())
            block = lines[push + 1:end]
            self.assertIn("    branches: [main]", block)
            self.assertIn("    paths:", block)
            actual = tuple(line.strip()[2:].strip("'\"") for line in block
                           if line.startswith("      - "))
            with self.subTest(workflow=filename):
                self.assertEqual(tuple(expected), actual,
                                 "Update the gate whenever a student's push filters change.")


class StudentGateWaitingTests(unittest.TestCase):
    def wait(self, client, expected=(WORKFLOW,), timeout=30):
        self.clock = Clock()
        return gate.wait_for_ci(set(expected), SHA, client, timeout=timeout, poll_interval=10,
                                clock=self.clock.now, sleep=self.clock.sleep)

    def test_delayed_creation_and_running_checks_are_waited_for_before_success(self):
        client = GithubFixture([[], [run(status="queued", conclusion=None)],
                                [run(status="in_progress", conclusion=None)], [run()]])
        self.assertTrue(self.wait(client, timeout=40))
        self.assertEqual(len(client.run_calls), 4)
        self.assertEqual(self.clock.sleeps, [10, 10, 10])

    def test_expected_check_that_never_appears_blocks_deployment(self):
        with self.assertRaises(gate.GateError):
            self.wait(GithubFixture([[]]))
        self.assertGreaterEqual(self.clock.elapsed, 30)
        self.assertLessEqual(self.clock.elapsed, 40)

    def test_running_check_that_exceeds_deadline_blocks_deployment(self):
        with self.assertRaises(gate.GateError):
            self.wait(GithubFixture([[run(status="in_progress", conclusion=None)]]))

    def test_non_successful_conclusions_never_pass_the_gate(self):
        for conclusion in ("failure", "cancelled", "timed_out", "skipped", "neutral", "action_required", None):
            with self.subTest(conclusion=conclusion), self.assertRaises(gate.GateError):
                self.wait(GithubFixture([[run(conclusion=conclusion)]]))

    def test_success_from_another_commit_event_or_branch_is_not_reused(self):
        for fields in ({"head_sha": "c" * 40}, {"head_branch": "feature"},
                       {"event": "pull_request"}, {"event": "workflow_dispatch"}):
            with self.subTest(fields=fields), self.assertRaises(gate.GateError):
                self.wait(GithubFixture([[run(**fields)]]))

    def test_newer_pending_run_is_not_replaced_by_an_older_success(self):
        client = GithubFixture([[run(1), run(2, status="in_progress", conclusion=None)],
                                [run(1), run(2)]])
        self.assertTrue(self.wait(client))
        self.assertEqual(len(client.run_calls), 2)
        self.assertEqual(self.clock.sleeps, [10])

    def test_newer_failed_run_is_not_replaced_by_an_older_success(self):
        with self.assertRaises(gate.GateError):
            self.wait(GithubFixture([[run(1), run(2, conclusion="failure")]]))

    def test_all_expected_students_must_pass(self):
        client = GithubFixture([[run()], [run(conclusion="failure")]])
        with self.assertRaises(gate.GateError):
            self.wait(client, expected=("student-1.yml", WORKFLOW))
        self.assertEqual({workflow for workflow, _ in client.run_calls},
                         {"student-1.yml", WORKFLOW})

    def test_stale_commit_is_skipped_without_querying_student_runs(self):
        client = GithubFixture(main=("c" * 40,))
        self.assertFalse(self.wait(client))
        self.assertEqual(client.run_calls, [])

    def test_new_main_commit_after_success_is_checked_before_deployment(self):
        client = GithubFixture([[run()]], main=(SHA, "c" * 40))
        self.assertFalse(self.wait(client))

    def test_no_expected_checks_still_requires_current_main(self):
        current = GithubFixture()
        self.assertTrue(self.wait(current, expected=()))
        self.assertEqual(current.run_calls, [])
        stale = GithubFixture(main=("c" * 40,))
        self.assertFalse(self.wait(stale, expected=()))

    def test_github_errors_are_not_converted_into_missing_or_successful_checks(self):
        for client in (GithubFixture(main=(gate.GateError("main API unavailable"),)),
                       GithubFixture([gate.GateError("workflow API unavailable")])):
            with self.subTest(client=client), self.assertRaises(gate.GateError):
                self.wait(client)


class GitAndGithubBoundariesTests(unittest.TestCase):
    def test_changed_paths_preserve_deleted_and_both_renamed_paths_with_nul_delimiters(self):
        result = subprocess.CompletedProcess([], 0, stdout="student-1/old file.py\0student-3/new file.py\0", stderr="")
        with patch.object(gate.subprocess, "run", return_value=result) as invoke:
            actual = gate.changed_paths(BEFORE, SHA)
        self.assertEqual(set(actual), {"student-1/old file.py", "student-3/new file.py"})
        command = invoke.call_args.args[0]
        self.assertIn("--no-renames", command)
        self.assertIn("-z", command)
        self.assertIn(BEFORE, command)
        self.assertIn(SHA, command)
        self.assertGreater(invoke.call_args.kwargs["timeout"], 0)
        self.assertLessEqual(invoke.call_args.kwargs["timeout"], 60)

    def test_git_failure_does_not_silently_produce_no_required_tests(self):
        with patch.object(gate.subprocess, "run", side_effect=subprocess.CalledProcessError(128, ["git"])):
            with self.assertRaises(gate.GateError):
                gate.changed_paths(BEFORE, SHA)

    def test_git_timeout_blocks_deployment(self):
        with patch.object(gate.subprocess, "run", side_effect=subprocess.TimeoutExpired(["git"], 30)):
            with self.assertRaises(gate.GateError):
                gate.changed_paths(BEFORE, SHA)

    def test_github_api_commands_have_a_bounded_timeout(self):
        result = subprocess.CompletedProcess([], 0, stdout=json.dumps({"sha": SHA}), stderr="")
        with patch.object(gate.subprocess, "run", return_value=result) as invoke:
            self.assertEqual(gate.Github("fixture/nextstop").latest_main(), SHA)
        self.assertGreater(invoke.call_args.kwargs["timeout"], 0)
        self.assertLessEqual(invoke.call_args.kwargs["timeout"], 60)

    def test_github_workflow_query_is_scoped_to_push_main_and_the_same_sha(self):
        result = subprocess.CompletedProcess([], 0, stdout=json.dumps({"workflow_runs": []}), stderr="")
        with patch.object(gate.subprocess, "run", return_value=result) as invoke:
            self.assertEqual(gate.Github("fixture/nextstop").workflow_runs(WORKFLOW, SHA), [])
        command = " ".join(invoke.call_args.args[0])
        self.assertIn("student-2.yml", command)
        self.assertIn("push", command)
        self.assertIn("main", command)
        self.assertIn(SHA, command)

    def test_invalid_git_revisions_never_execute_a_command(self):
        for before, sha in ((None, SHA), ("main", SHA), (BEFORE, "HEAD"), (BEFORE, "0" * 40)):
            with self.subTest(before=before, sha=sha), patch.object(gate.subprocess, "run") as invoke:
                with self.assertRaises(gate.GateError):
                    gate.changed_paths(before, sha)
                invoke.assert_not_called()

    def test_new_main_branch_checks_the_entire_tree(self):
        result = subprocess.CompletedProcess([], 0, stdout="student-1/api.py\0student-2/api.py\0", stderr="")
        with patch.object(gate.subprocess, "run", return_value=result) as invoke:
            self.assertEqual(gate.changed_paths("0" * 40, SHA), ["student-1/api.py", "student-2/api.py"])
        self.assertEqual(invoke.call_args.args[0], ["git", "ls-tree", "-r", "--name-only", "-z", SHA])

    def test_github_timeout_and_malformed_response_block_deployment(self):
        for result in (subprocess.TimeoutExpired(["gh"], 30),
                       subprocess.CompletedProcess([], 0, stdout="not json", stderr=""),
                       subprocess.CompletedProcess([], 0, stdout="[]", stderr="")):
            with self.subTest(result=result):
                arguments = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
                with patch.object(gate.subprocess, "run", **arguments), self.assertRaises(gate.GateError):
                    gate.Github("fixture/nextstop").latest_main()


class StudentGateEntryPointTests(unittest.TestCase):
    def entrypoint(self, **variables):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "github-output"
        self.env = {"EVENT": "push", "SHA": SHA, "BEFORE_SHA": BEFORE,
                    "GITHUB_REPOSITORY": "fixture/nextstop", "GITHUB_OUTPUT": str(self.output),
                    **variables}
        return gate.main(self.env)

    def test_manual_run_preserves_bypass_without_git_or_github(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "github-output"
            with patch.object(gate, "changed_paths") as changed, patch.object(gate, "Github") as github:
                result = gate.main({"EVENT": "workflow_dispatch", "GITHUB_OUTPUT": str(output)})
            self.assertEqual(result, 0)
            self.assertEqual(output.read_text(), "ok=true\n")
            changed.assert_not_called()
            github.assert_not_called()

    def test_push_uses_before_sha_path_selection_and_exports_success(self):
        client = GithubFixture([[run()]])
        with patch.object(gate, "Github", return_value=client) as github, \
                patch.object(gate, "changed_paths", return_value=["student-2/api.py"]) as changed:
            self.assertEqual(self.entrypoint(), 0)
        github.assert_called_once_with("fixture/nextstop")
        changed.assert_called_once_with(BEFORE, SHA)
        self.assertEqual(client.run_calls, [(WORKFLOW, SHA)])
        self.assertEqual(self.output.read_text(), "ok=true\n")

    def test_failed_required_check_exports_false_and_fails_the_step(self):
        with patch.object(gate, "Github", return_value=GithubFixture([[run(conclusion="failure")]])), \
                patch.object(gate, "changed_paths", return_value=["student-2/api.py"]):
            self.assertEqual(self.entrypoint(), 1)
        self.assertEqual(self.output.read_text(), "ok=false\n")

    def test_stale_push_exports_false_without_diffing_its_old_history(self):
        with patch.object(gate, "Github", return_value=GithubFixture(main=("c" * 40,))), \
                patch.object(gate, "changed_paths") as changed:
            self.assertEqual(self.entrypoint(), 0)
        self.assertEqual(self.output.read_text(), "ok=false\n")
        changed.assert_not_called()

    def test_pull_request_and_workflow_run_cannot_enter_the_deployment_gate(self):
        for event in ("pull_request", "workflow_run"):
            with self.subTest(event=event), patch.object(gate, "Github") as github:
                self.assertEqual(self.entrypoint(EVENT=event), 1)
                self.assertEqual(self.output.read_text(), "ok=false\n")
                github.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
