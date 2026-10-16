# Release 2 Technical Report - Group 25

**41026 Advanced Software Development, Spring 2026**
**Project NextStop - Agentic AI travel planning application**

---

## Pre-commit security testing **(Group)**

Owner Aurelia Sari

Every commit runs three local scans from `.pre-commit-config.yaml`. Each hook
calls `security/run_scan.py`, which runs one pytest file per scan, so a failure
shows the tool output as a readable assertion message. Any finding blocks the
commit.

| Hook | Tool | Runs |
|------|------|------|
| `ruff-security` | Ruff `S` rules (flake8-bandit), S101 ignored in tests | every commit, whole repository |
| `detect-secrets` | detect-secrets against `.secrets.baseline` | every commit, all tracked files |
| `pip-audit` | pip-audit on every `requirements*.txt` | only when a requirements file is staged |

pip-audit queries an online vulnerability database, so it is slow and fails
offline. Its hook sets `files` to match `requirements*.txt`, and pre-commit
skips a hook when no staged file matches. The other two hooks set
`always_run`.

The first full scan found 63 Ruff findings, 77 possible secrets, and known
vulnerabilities in every pinned requirements file.

- **Dependencies.** Flask 3.1.3, flask-cors 6.0.5, requests 2.34.2, Werkzeug
  3.1.9 and pytest 9.1.1 replaced the vulnerable pins in every service. Two
  unpinned `requests` lines were pinned so they can be audited.
- **Ruff.** Seven student-2 database calls had no timeout and now use 10
  seconds. The other 56 were reviewed false positives, such as containers
  binding to `0.0.0.0` and SQL built only from fixed column lists with bound
  values. Each has a one line `noqa` with its reason.
- **Secrets.** All 77 were public Google Maps photo references or documented
  seed and test passwords, recorded in the baseline as reviewed.

Every unit test, smoke test and frontend check gave the same result before and
after these changes. The full scan output is in
`docs/evidence/pre-commit-security-scan.txt`.
