"""Wait for the student push checks required by this main push before deployment."""

import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


# Contract tests keep these filters in sync with the existing student workflows.
WORKFLOW_PATHS = {
    f"student-{number}.yml": (
        f"student-{number}/**", "shared/**", "ai-services/**", "scripts/**",
        "docker-compose.yml", f".github/workflows/student-{number}.yml",
    )
    for number in range(1, 6)
}


class GateError(Exception):
    """Required CI could not be verified successfully."""


def expected_workflows(paths):
    return {
        workflow for workflow, patterns in WORKFLOW_PATHS.items()
        if any(fnmatch.fnmatchcase(path, pattern) for path in paths for pattern in patterns)
    }


def changed_paths(before, sha):
    for revision in (before, sha):
        if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", revision or ""):
            raise GateError("The push must provide valid before and head commit SHAs.")
    if set(sha) == {"0"}:
        raise GateError("A branch deletion cannot be deployed.")
    if set(before) == {"0"}:
        command = ["git", "ls-tree", "-r", "--name-only", "-z", sha]
    else:
        # A move must count both its old and new paths when selecting checks.
        command = ["git", "diff", "--no-renames", "--name-only", "-z", before, sha, "--"]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise GateError("Could not determine the files changed by this push.") from exc
    return [path for path in result.stdout.split("\0") if path]


class Github:
    def __init__(self, repository):
        self.repository = repository

    def _json(self, endpoint):
        try:
            result = subprocess.run(
                ["gh", "api", endpoint], check=True, capture_output=True, text=True, timeout=30,
            )
            value = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise GateError(f"GitHub API request failed: {endpoint}") from exc
        if not isinstance(value, dict):
            raise GateError("GitHub returned an unexpected response.")
        return value

    def latest_main(self):
        value = self._json(f"repos/{self.repository}/commits/main").get("sha")
        if not value:
            raise GateError("GitHub did not return the current main commit.")
        return value

    def workflow_runs(self, workflow, sha):
        endpoint = (
            f"repos/{self.repository}/actions/workflows/{workflow}/runs"
            f"?event=push&branch=main&head_sha={sha}&per_page=100"
        )
        runs = self._json(endpoint).get("workflow_runs")
        if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
            raise GateError("GitHub did not return a list of workflow runs.")
        return runs


def latest_run(runs, sha):
    matching = [run for run in runs if run.get("head_sha") == sha
                and run.get("event") == "push" and run.get("head_branch") == "main"]
    return max(matching, key=lambda run: run["id"], default=None)


def wait_for_ci(expected, sha, client, *, timeout=1200, poll_interval=10,
                clock=time.monotonic, sleep=time.sleep):
    if timeout <= 0 or poll_interval <= 0:
        raise GateError("CI wait and polling intervals must be positive.")
    deadline = clock() + timeout
    reported = {}
    while True:
        if client.latest_main() != sha:
            print("A newer main commit exists; skipping this deployment.", flush=True)
            return False
        pending = []
        for workflow in sorted(expected):
            run = latest_run(client.workflow_runs(workflow, sha), sha)
            state = "not created yet" if run is None else run.get("status", "unknown")
            if state == "completed":
                state = run.get("conclusion")
                if state != "success":
                    raise GateError(f"{workflow} did not succeed ({state}); not deploying.")
            else:
                pending.append(workflow)
            if reported.get(workflow) != state:
                print(f"{workflow} -> {state}", flush=True)
                reported[workflow] = state
        if clock() >= deadline:
            raise GateError("Timed out waiting for required student CI: " + ", ".join(pending))
        if not pending:
            # The branch can advance while student API calls are in flight.
            if client.latest_main() != sha:
                print("A newer main commit exists; skipping this deployment.", flush=True)
                return False
            return True
        remaining = deadline - clock()
        if remaining <= 0:
            raise GateError("Timed out waiting for required student CI: " + ", ".join(pending))
        sleep(min(poll_interval, remaining))


def main(environ=None):
    env = os.environ if environ is None else environ

    def output(ok):
        with Path(env["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            stream.write(f"ok={str(ok).lower()}\n")

    try:
        if env.get("EVENT") == "workflow_dispatch":
            print("Manual run, skipping student CI gate.")
            output(True)
            return 0
        if env.get("EVENT") != "push":
            raise GateError("Only a main push or a manual run can deploy.")
        sha = env["SHA"]
        client = Github(env["GITHUB_REPOSITORY"])
        if client.latest_main() != sha:
            print("A newer main commit exists; skipping this queued deployment.")
            output(False)
            return 0
        expected = expected_workflows(changed_paths(env.get("BEFORE_SHA"), sha))
        print("Required student checks: " + (", ".join(sorted(expected)) or "none for these paths"))
        output(wait_for_ci(expected, sha, client))
        return 0
    except (GateError, KeyError) as exc:
        print(f"Student CI gate failed: {exc}", file=sys.stderr)
        output(False)
        return 1


if __name__ == "__main__":
    sys.exit(main())
