# student-4 tests

This feature is validated through `scripts/smoke_test.py 4`, which the
`student-4` GitHub Actions workflow runs against the live services. It
dispatches to `student-4/tests/smoke_test.py`, a dedicated script rather than
a generic CRUD check, sign-up, email verification and sign-in don't fit the
create/read/update/delete-on-one-resource shape the generic smoke test
assumes (see `scripts/smoke_test.py`'s `check_student_4()` for why, and
`docs/technical-report.md` 2.6 R4-6).

```bash
docker compose up -d student-4-db student-4-api shared-api shared-db mailpit
python3 scripts/smoke_test.py 4
# or directly:
python3 student-4/tests/smoke_test.py
```

It exercises the real flow end to end:

- **Sign-up.** Registration validation (missing T&C, weak password, invalid
  email), duplicate-email rejection, and the accounts listing.
- **Email verification.** By polling Mailpit's API for the actual email and
  extracting the link from it, full verification including single-use
  enforcement and the resend rate limit.
- **Sign-in.** `POST /auth/login` returns the same generic "Invalid email or
  password." for both a wrong password and an email with no account (no
  account enumeration), returns 403 with `error_code: "email_not_verified"`
  for a correct password on an unverified account, and returns 200 with the
  user (never the password hash) once the account is verified. Also checks
  that an unverified sign-in attempt made within the 60s resend cooldown
  does not trigger a duplicate verification email.
- **Sign-out and session status.** `GET /auth/status/<id>` reports
  `is_valid: true` right after login, `POST /auth/logout` closes that
  session (`is_valid` flips to `false` and `last_logout` is stamped), and a
  second logout on the same (now-closed) session returns 404. This is the
  same contract any other feature uses to check whether a user is signed in,
  documented in `docs/ADR-001-service-boundaries.md`, Decision 6.

Each run registers freshly-randomised email addresses, so it is safe to
re-run without leaving stray state behind; there is deliberately no
account-delete endpoint to clean up with instead.

**Not covered by the automated script** (would need a >60s sleep to clear the
resend cooldown, which the existing resend test also avoids for the same
reason): that a sign-in attempt *outside* the cooldown actually sends a fresh
verification email. Verified manually instead, `POST /auth/login` for an
unverified account, then Mailpit's API confirms a new message arrives with
the verification link.

Release 2 requires pre-commit `pytest` validation and post-commit AI-assisted
unit testing (project specification, section 7.3). Unit tests for this feature
belong in this directory.
