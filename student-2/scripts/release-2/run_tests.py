"""Lab 11-style runner: execute tests and record actual results, never fabricated PASS."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["post_commit"])
    args = parser.parse_args()
    folder = ROOT / "reports/release-2"
    folder.mkdir(parents=True, exist_ok=True)
    target = "tests/release-2/post_commit"
    command = [sys.executable, "-m", "pytest", target, "-v", "--tb=short",
               "--basetemp", "reports/release-2/.pytest-tmp", f"--junitxml=reports/release-2/{args.stage}.xml"]
    with tempfile.TemporaryDirectory(prefix=".pytest-", dir=folder) as temp:
        command[command.index("--basetemp") + 1] = str(Path(temp) / "work")
        result = subprocess.run(  # noqa: S603 fixed pytest invocation; stage limited to known suites
            command, cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True)
    output = result.stdout + result.stderr
    print(output)
    (folder / f"{args.stage}-console.txt").write_text(output)
    stamp = datetime.now(timezone.utc).isoformat()
    status = "PASS" if result.returncode == 0 else "FAIL"
    context = {key: os.environ.get(key) for key in
               ("GITHUB_SHA", "GITHUB_REF", "GITHUB_HEAD_REF", "GITHUB_BASE_REF",
                "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME")
               if os.environ.get(key)}
    server, repository, run_id = (os.getenv(key) for key in
                                  ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    if server and repository and run_id:
        context["run_url"] = f"{server}/{repository}/actions/runs/{run_id}"
    entry = {"timestamp": stamp, "stage": args.stage, "status": status,
             "exit_code": result.returncode, "command": command,
             "api_url": os.getenv("STUDENT2_API_URL", "http://localhost:5102"),
             "execution": "github-actions" if os.getenv("GITHUB_ACTIONS") == "true" else "local",
             **context}
    with (folder / "test-audit.jsonl").open("a") as file:
        file.write(json.dumps(entry) + "\n")
    with (folder / "test-results.md").open("a") as file:
        file.write(f"\n## {stamp} — {args.stage}: {status}\n\n"
                   f"Execution: {entry['execution']}. Exit code: {result.returncode}.\n\n"
                   f"See `{args.stage}-console.txt` and `{args.stage}.xml`.\n")
        if context.get("GITHUB_SHA"):
            file.write(f"Commit: {context['GITHUB_SHA']}\n\n")
        if context.get("run_url"):
            file.write(f"CI run: {context['run_url']}\n")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
