"""Run one pre-commit security scan through its pytest file.

Usage
    python security/run_scan.py ruff
    python security/run_scan.py secrets
    python security/run_scan.py pip_audit
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANS = ("ruff", "secrets", "pip_audit")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SCANS:
        sys.exit("usage python security/run_scan.py " + " | ".join(SCANS))
    test_file = ROOT / "security" / "tests" / f"test_{sys.argv[1]}.py"
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test_file)]
    sys.exit(subprocess.call(command, cwd=ROOT))  # noqa: S603 fixed command built from a known scan name


if __name__ == "__main__":
    main()
