import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / ".secrets.baseline"


def _findings(baseline):
    return {
        (path.replace("\\", "/"), secret["hashed_secret"]): f"{path} line {secret['line_number']} {secret['type']}"
        for path, secrets in baseline["results"].items()
        for secret in secrets
    }


def test_no_new_secrets(tmp_path):
    assert BASELINE.exists(), "missing .secrets.baseline, create it with detect-secrets scan > .secrets.baseline"
    known = _findings(json.loads(BASELINE.read_text(encoding="utf-8")))

    # Scanning against a copy reuses the baseline plugins and filters without rewriting the real file
    scratch = tmp_path / "baseline.json"
    shutil.copy(BASELINE, scratch)
    result = subprocess.run(  # noqa: S603 fixed command with no user input
        [sys.executable, "-m", "detect_secrets", "scan", "--baseline", str(scratch),
         "--exclude-files", r"^\.secrets\.baseline$"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, "detect-secrets failed\n\n" + result.stdout + result.stderr

    current = _findings(json.loads(scratch.read_text(encoding="utf-8")))
    new = [label for key, label in current.items() if key not in known]
    assert not new, (
        "Possible secrets not in .secrets.baseline\n\n" + "\n".join(sorted(new))
        + "\n\nRemove the secret, or if it is a false positive run detect-secrets audit .secrets.baseline"
    )
