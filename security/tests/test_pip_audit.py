import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = sorted(
    path.relative_to(ROOT).as_posix()
    for path in ROOT.rglob("requirements*.txt")
    if not any(part.startswith(".") or part == "node_modules" for part in path.relative_to(ROOT).parts)
)


@pytest.mark.parametrize("requirements", REQUIREMENTS)
def test_no_known_vulnerabilities(requirements):
    result = subprocess.run(  # noqa: S603 fixed command, the path comes from the repository tree
        [sys.executable, "-m", "pip_audit", "-r", requirements, "--no-deps", "--disable-pip",
         "--progress-spinner", "off"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, f"pip-audit findings in {requirements}\n\n" + result.stdout + result.stderr
