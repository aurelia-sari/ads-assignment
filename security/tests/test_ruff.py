import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ruff_security_rules_pass():
    result = subprocess.run(  # noqa: S603 fixed command with no user input
        [sys.executable, "-m", "ruff", "check", "--output-format", "concise", "."],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, "Ruff security findings\n\n" + result.stdout + result.stderr
