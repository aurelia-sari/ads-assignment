# student-4 tests

Release 0 validates this feature through `scripts/smoke_test.py 4`, which the
`student-4` GitHub Actions workflow runs against the live services. It
dispatches to `student-4/tests/smoke_test.py`, a dedicated script rather than
a generic CRUD check, sign-up and email verification don't fit the
create/read/update/delete-on-one-resource shape the generic smoke test
assumes (see `scripts/smoke_test.py`'s `check_student_4()` for why, and
`docs/technical-report.md` 2.6 R4-6).

```bash
docker compose up -d student-4-db student-4-api shared-api shared-db mailpit
python3 scripts/smoke_test.py 4
# or directly:
python3 student-4/tests/smoke_test.py
```

It exercises the real flow end to end: registration validation (missing T&C,
weak password, invalid email), duplicate-email rejection, the accounts
listing, and by polling Mailpit's API for the actual email and extracting
the link from it, full email verification including single-use enforcement
and the resend rate limit. Each run registers freshly-randomised email
addresses, so it is safe to re-run without leaving stray state behind; there
is deliberately no account-delete endpoint to clean up with instead.

Release 2 requires pre-commit `pytest` validation and post-commit AI-assisted
unit testing (project specification, section 7.3). Unit tests for this feature
belong in this directory.
