"""Exercise deployment command boundaries without SSH, rsync, or a real VM."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = Path(os.getenv("CLOUD_DEPLOY_SCRIPT", ROOT / "deploy/azure/deploy.sh"))
REMOTE_SCRIPT = ROOT / "deploy/azure/deploy_remote.sh"
CONFIGURE_SCRIPT = ROOT / "deploy/azure/configure_ai.sh"


class DeploymentCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nextstop-deploy-test-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.log = self.folder / "commands.jsonl"
        helper = self.folder / "command_stub.py"
        helper.write_text('''import json, os, pathlib, sys
name, *args = sys.argv[1:]
record = {"tool": name, "args": args,
          "flags": [os.environ.get(key) for key in
                    ("AI_MODE_ENABLED", "MCP_ENABLED", "RAG_ENABLED", "MULTI_AGENT_ENABLED")]}
if name == "sudo" and args == ["tee", "/etc/nextstop/ai.env"]:
    record["ai_environment"] = sys.stdin.read()
if name == "mv":
    record["selection"] = pathlib.Path(args[0]).read_text()
with open(os.environ["DEPLOY_TEST_LOG"], "a", encoding="utf-8") as output:
    output.write(json.dumps(record) + "\\n")
if name == "ssh" and "cloud-init status" in args[-1]:
    sys.exit(int(os.environ.get("DEPLOY_TEST_READY_STATUS", "0")))
if name == "ssh" and "cloud-ai-selection" in args[-1]:
    sys.stdout.write(os.environ.get("DEPLOY_TEST_STORED_SELECTION", "false\\nllama3.2:latest\\n"))
    sys.exit(int(os.environ.get("DEPLOY_TEST_SELECTION_STATUS", "0")))
if name == "rsync":
    sys.exit(int(os.environ.get("DEPLOY_TEST_RSYNC_STATUS", "0")))
if name == "bash" and args == ["deploy/azure/configure_ai.sh", "start"]:
    sys.exit(int(os.environ.get("DEPLOY_TEST_AI_START_STATUS", "0")))
if name == "python3":
    sys.exit(int(os.environ.get("DEPLOY_TEST_HEALTH_STATUS", "0")))
if name == "mktemp":
    print(os.environ["DEPLOY_TEST_SELECTION_TMP"])
if name == "gh":
    print(os.environ["DEPLOY_TEST_MAIN_SHA"] if args[0] == "api" else "success")
sys.exit(0)
''')
        for name in ("ssh", "rsync", "sleep", "docker", "dpkg", "bash", "python3", "sudo", "mkdir", "curl", "ollama", "mktemp", "mv", "gh"):
            stub = self.folder / name
            stub.write_text(
                "#!/bin/sh\nexec " + shlex.quote(sys.executable) + " "
                + shlex.quote(str(helper)) + " " + shlex.quote(name) + ' "$@"\n'
            )
            stub.chmod(0o755)
        self.env = dict(os.environ)
        for key in ("ENABLE_CLOUD_AI", "CLOUD_OLLAMA_MODEL", "DEPLOY_TEST_READY_STATUS", "DEPLOY_TEST_RSYNC_STATUS", "DEPLOY_TEST_AI_START_STATUS", "DEPLOY_TEST_HEALTH_STATUS", "DEPLOY_TEST_STORED_SELECTION", "DEPLOY_TEST_SELECTION_STATUS"):
            self.env.pop(key, None)
        self.env.update({
            "PATH": str(self.folder) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            "VM_HOST": "cloud.example.test",
            "SSH_KEY": str(self.folder / "deployment key"),
            "DEPLOY_TEST_LOG": str(self.log),
            "DEPLOY_TEST_SELECTION_TMP": str(self.folder / "selection.tmp"),
            "DEPLOY_TEST_MAIN_SHA": "current-main-sha",
            "GITHUB_REPOSITORY": "fixture/nextstop",
            "SHA": "current-main-sha",
            "EVENT": "workflow_run",
            "GITHUB_OUTPUT": str(self.folder / "github-output"),
            "GITHUB_ENV": str(self.folder / "github-env"),
        })

    def run_script(self, script, arguments=(), **environment):
        result = subprocess.run(
            ["/bin/bash", str(script), *arguments], env={**self.env, **environment},
            capture_output=True, text=True, timeout=20, check=False,
        )
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def run_deploy(self, **environment):
        return self.run_script(DEPLOY_SCRIPT, **environment)

    def run_workflow_step(self, name, **environment):
        lines = (ROOT / ".github/workflows/cloud-deployment.yml").read_text().splitlines()
        start = lines.index("      - name: " + name)
        run = next(index for index in range(start + 1, len(lines)) if lines[index] == "        run: |")
        script_lines = []
        for line in lines[run + 1:]:
            if line and not line.startswith("          "):
                break
            script_lines.append(line[10:] if line else "")
        script = self.folder / "workflow-step.sh"
        script.write_text("set -eo pipefail\n" + "\n".join(script_lines) + "\n")
        return self.run_script(script, **environment)

    @staticmethod
    def remote_arguments(calls):
        remote = [call for call in calls if call["tool"] == "ssh" and "deploy_remote.sh" in call["args"][-1]]
        if len(remote) != 1:
            raise AssertionError(f"Expected one remote deployment, received {remote!r}")
        return shlex.split(remote[0]["args"][-1])[-3:]

    def test_invalid_enable_value_is_rejected_before_any_network_command(self):
        result, calls = self.run_deploy(ENABLE_CLOUD_AI="yes")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("true or false", result.stderr)
        self.assertEqual(calls, [])

    def test_invalid_host_and_model_are_rejected_before_any_network_command(self):
        for variable, value in (("VM_HOST", "host;unexpected"), ("CLOUD_OLLAMA_MODEL", "model;unexpected")):
            with self.subTest(variable=variable):
                result, calls = self.run_deploy(**{variable: value})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(calls, [])

    def test_readiness_failure_never_syncs_or_deploys(self):
        result, calls = self.run_deploy(DEPLOY_TEST_READY_STATUS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VM did not become ready", result.stderr)
        ssh = [call for call in calls if call["tool"] == "ssh"]
        self.assertEqual(len(ssh), 30)
        self.assertTrue(all("cloud-init status" in call["args"][-1] for call in ssh))
        self.assertFalse(any(call["tool"] == "rsync" for call in calls))

    def test_sync_includes_ai_source_and_protects_vm_state(self):
        result, calls = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        sync = [call["args"] for call in calls if call["tool"] == "rsync"]
        self.assertEqual(len(sync), 1)
        args = sync[0]
        excludes = [args[index + 1] for index, arg in enumerate(args) if arg == "--exclude"]
        for protected in (".env", ".venv", ".runtime", "*.db"):
            self.assertIn(protected, excludes)
        self.assertNotIn("ai-services", excludes)
        self.assertNotIn("ai-services/", excludes)
        self.assertIn("--delete", args)
        self.assertEqual(args[-2:], ["./", "azureuser@cloud.example.test:~/nextstop/"])
        transport = shlex.split(args[args.index("-e") + 1])
        self.assertEqual(transport[transport.index("-i") + 1], self.env["SSH_KEY"])

    def test_default_deployment_keeps_cloud_ai_disabled(self):
        result, calls = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.remote_arguments(calls), ["false", "llama3.2:latest", "cloud.example.test"])

    def test_enabled_deployment_forwards_selected_model_safely(self):
        model = "hf.co/example/model:Q4_K_M"
        result, calls = self.run_deploy(ENABLE_CLOUD_AI="true", CLOUD_OLLAMA_MODEL=model)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.remote_arguments(calls), ["true", model, "cloud.example.test"])

    def test_sync_failure_never_runs_remote_deployment(self):
        result, calls = self.run_deploy(DEPLOY_TEST_RSYNC_STATUS="23")
        self.assertEqual(result.returncode, 23)
        self.assertFalse(any(call["tool"] == "ssh" and "deploy_remote.sh" in call["args"][-1] for call in calls))


    def test_remote_enabled_starts_one_shared_stack_and_builds_once(self):
        result, calls = self.run_script(REMOTE_SCRIPT, ("true", "llama3.2:latest", "cloud.example.test"))
        self.assertEqual(result.returncode, 0, result.stderr)
        configure = [call for call in calls if call["tool"] == "bash"]
        self.assertEqual([call["args"] for call in configure], [
            ["deploy/azure/configure_ai.sh", "stop"], ["deploy/azure/configure_ai.sh", "start"],
        ])
        builds = [call for call in calls if call["tool"] == "docker" and "up" in call["args"]]
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0]["flags"], ["true"] * 4)
        self.assertIn("--build", builds[0]["args"])
        self.assertLess(calls.index(configure[-1]), calls.index(builds[0]))
        self.assertFalse(any("smoke_test.py" in " ".join(call["args"]) for call in calls))
        saved = [call for call in calls if call["tool"] == "mv"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["selection"], "true\nllama3.2:latest\n")
        self.assertTrue(saved[0]["args"][-1].endswith("/.local/share/nextstop/cloud-ai-selection"))
        self.assertLess(calls.index(builds[0]), calls.index(saved[0]))

    def test_remote_baseline_stops_shared_ai_and_builds_disabled_once(self):
        result, calls = self.run_script(REMOTE_SCRIPT, ("false", "llama3.2:latest", "cloud.example.test"))
        self.assertEqual(result.returncode, 0, result.stderr)
        configure = [call["args"] for call in calls if call["tool"] == "bash"]
        self.assertEqual(configure, [["deploy/azure/configure_ai.sh", "stop"]])
        builds = [call for call in calls if call["tool"] == "docker" and "up" in call["args"]]
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0]["flags"], ["false"] * 4)
        saved = [call for call in calls if call["tool"] == "mv"]
        self.assertEqual(saved[0]["selection"], "false\nllama3.2:latest\n")

    def test_shared_ai_start_failure_stops_before_container_update(self):
        result, calls = self.run_script(
            REMOTE_SCRIPT, ("true", "llama3.2:latest", "cloud.example.test"),
            DEPLOY_TEST_AI_START_STATUS="7",
        )
        self.assertEqual(result.returncode, 7)
        self.assertFalse(any(call["tool"] in ("mktemp", "mv") for call in calls))
        self.assertFalse(any(call["tool"] == "docker" for call in calls))

    def test_application_readiness_failure_remains_a_failed_deploy(self):
        result, calls = self.run_script(
            REMOTE_SCRIPT, ("true", "llama3.2:latest", "cloud.example.test"),
            DEPLOY_TEST_HEALTH_STATUS="8",
        )
        self.assertEqual(result.returncode, 8)
        self.assertFalse(any(call["tool"] in ("mktemp", "mv") for call in calls))
        self.assertFalse(any(call["tool"] == "docker" and call["args"][-1] == "ps" for call in calls))

    def test_invalid_ai_model_is_rejected_before_install_or_service_actions(self):
        result, calls = self.run_script(CONFIGURE_SCRIPT, ("start",), CLOUD_OLLAMA_MODEL="model;unexpected")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Invalid model name", result.stderr)
        self.assertEqual(calls, [])

    def test_cloud_environment_extends_only_the_worker_generation_budget(self):
        result, calls = self.run_script(CONFIGURE_SCRIPT, ("start",))
        self.assertEqual(result.returncode, 0, result.stderr)
        environments = [call["ai_environment"] for call in calls if "ai_environment" in call]
        self.assertEqual(len(environments), 1)
        settings = dict(line.split("=", 1) for line in environments[0].splitlines())
        self.assertEqual(settings["CLOUD_WORKER_TIMEOUT_SECONDS"], "360")
        self.assertEqual(settings["CLOUD_CITATION_VALIDATION"], "true")
        self.assertEqual(settings["MULTI_AGENT_ASYNC_ENABLED"], "true")
        self.assertNotIn("MULTI_AGENT_LLM_TIMEOUT", settings)
        self.assertNotIn("RAG_REQUEST_TIMEOUT_SECONDS", settings)

    def test_invalid_remote_model_does_not_stop_services_or_install_packages(self):
        result, calls = self.run_script(REMOTE_SCRIPT, ("true", "model;unexpected", "cloud.example.test"))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(calls, [])

    def test_automatic_deployment_retains_previous_manual_selection(self):
        result, calls = self.run_workflow_step(
            "Retain cloud AI selection for automatic deployments",
            DEPLOY_TEST_STORED_SELECTION="true\nhf.co/example/model:Q4_K_M\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(self.env["GITHUB_ENV"]).read_text(),
                         "ENABLE_CLOUD_AI=true\nCLOUD_OLLAMA_MODEL=hf.co/example/model:Q4_K_M\n")
        self.assertEqual([call["tool"] for call in calls], ["ssh"])

    def test_first_automatic_deployment_receives_disabled_default(self):
        result, calls = self.run_workflow_step("Retain cloud AI selection for automatic deployments")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(self.env["GITHUB_ENV"]).read_text(),
                         "ENABLE_CLOUD_AI=false\nCLOUD_OLLAMA_MODEL=llama3.2:latest\n")
        self.assertIn('else printf "false\\nllama3.2:latest\\n"', calls[0]["args"][-1])

    def test_invalid_stored_selection_does_not_export_deployment_settings(self):
        for stored in ("yes\nllama3.2:latest\n", "true\nmodel;unexpected\n", "true\nmodel\nEXTRA=value\n", "true\n"):
            with self.subTest(stored=stored):
                result, _ = self.run_workflow_step(
                    "Retain cloud AI selection for automatic deployments",
                    DEPLOY_TEST_STORED_SELECTION=stored,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(Path(self.env["GITHUB_ENV"]).exists())

    def test_failed_selection_read_never_silently_disables_ai(self):
        result, _ = self.run_workflow_step(
            "Retain cloud AI selection for automatic deployments", DEPLOY_TEST_SELECTION_STATUS="255",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(Path(self.env["GITHUB_ENV"]).exists())

    def test_stale_automatic_commit_is_skipped_before_student_gate_checks(self):
        result, calls = self.run_workflow_step("Gate on student CI/CD workflows", SHA="old-commit-sha")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_text(), "ok=false\n")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "gh")
        self.assertEqual(calls[0]["args"][0], "api")

    def test_current_automatic_commit_requires_the_existing_student_gate(self):
        result, calls = self.run_workflow_step("Gate on student CI/CD workflows")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_text(), "ok=true\n")
        self.assertEqual(len([call for call in calls if call["tool"] == "gh" and call["args"][0] == "run"]), 5)

    def test_manual_selection_is_not_replaced_by_a_previous_automatic_setting(self):
        result, calls = self.run_workflow_step("Gate on student CI/CD workflows", EVENT="workflow_dispatch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [])
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_text(), "ok=true\n")

if __name__ == "__main__":
    unittest.main(verbosity=2)
