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

The sign in gate checks described below also need `student-4-frontend` and
`shared-frontend` running to do anything. Add them to the `docker compose up`
line above if you want that part to run instead of skip:

```bash
docker compose up -d student-4-db student-4-api shared-api shared-db mailpit student-4-frontend shared-frontend
```

It exercises the real flow end to end:

- **Travel Guides.** `GET /guides` lists the five Australian and five
  Japanese destinations and supports searching by city or country, with a
  not-found placeholder
  for an unmatched search. `GET /guides/<id>` returns the destination's
  detail view (a back-to-list link, then a Currency, Transportation, Visa,
  Weather and Safety subsection). `GET /guides/<id>/transportation?type=`,
  `/visa?nationality=` and `/weather?month=` switch the active tab within
  each subsection, confirming a city only shows the transport modes it
  actually has (e.g. Nara has no metro or flights tab), that a booking
  button shows only on the Flights tab of a city student-5 can book (so not
  for Japan), that each country has its own currency and visa rules, that no
  visa nationality is selected by
  default since it cannot be guessed, and that the weather tab defaults to
  the city's own current month (Tokyo's month, not the server's UTC month).
  `GET /guides/<id>/safety` and the other per-destination
  endpoints return a graceful not-found message, not an error, for an
  unknown id.
- **Seed data.** The `student1`-`student5` and `traveller6`-`traveller10`
  accounts from `shared/db/init_db.py` are present, `student1` can sign in,
  and `traveller6` is still pending verification. Confirms the seed is baked
  into the image rather than only existing on one machine's Docker volume.
- **Sign-up.** Registration validation (missing T&C, weak password, invalid
  email) and duplicate-email rejection. Account listing is intentionally not
  exposed through the website, only through the database directly, so there
  is no accounts fragment to check here.
- **Email verification.** By polling Mailpit's API for the actual email and
  extracting the link from it, full verification including single-use
  enforcement and the resend rate limit.
- **Forgot / reset password.** `POST /auth/forgot-password` returns the same
  response whether or not the email is registered, so the flow cannot be used
  to probe which emails have accounts. By using Mailpit for the actual
  reset email and extracting the token from its link, confirms the token
  validates, a mismatched confirmation and a weak password are rejected,
  a valid reset actually changes the password (old password then fails,
  new password then succeeds), the token is single-use, and the resend
  rate limit matches email verification's.
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
- **Sign in gate on the frontend pages.** The landing page
  (`student-4/frontend/templates/index.html`) is confirmed to call
  `verifySession` before it shows its content, and the sign up, sign in,
  verify pending, forgot password, forgot password pending and reset
  password pages are confirmed to stay reachable without a session.
  The shared home page (`shared/index.html`, served on port 8080) is
  confirmed to load `shared/js/auth-guard.js`, the same guard the other four
  feature pages load. This step needs a real browser to check the actual
  redirect, so it is a static check on the served HTML rather than a click
  through test, and it skips itself with a printed note when
  student-4-frontend or shared-frontend are not running.
- **Logout page is served.** `logout.html` is fetched directly and
  checked for its one-time `justLoggedOut` sessionStorage gate,
  fails the smoke test instead of only showing up when someone clicks
  sign out.
- **Release 1 MCP and RAG.** The checks follow `GET /ai-tools/status`. In
  CI both servers are disabled, so the smoke test asserts the clear disabled
  response. Locally, with `./scripts/ai_services.sh up`, it asserts a live
  `lookup_destination_guide` call, a `schema-checked` boundary refusal for an
  empty query, and the insufficient-context reply for an off-topic question.
  The landing page is also checked for the MCP tools and Ask (grounded) tabs.
- **Live rates and weather.** `/guides/<id>/currency/live` and
  `/guides/<id>/weather/live` are checked in whichever state they report. In
  CI `GUIDES_LIVE_DATA=false`, so the switched off note is asserted. Locally
  the real Frankfurter rates and Open-Meteo conditions are asserted, or the
  unavailable note if the internet is down.

Each run registers freshly-randomised email addresses, so it is safe to
re-run without leaving stray state behind. There is deliberately no
account-delete endpoint to clean up with instead.

**Not covered by the automated script** (would need a >60s sleep to clear the
resend cooldown, which the existing resend test also avoids for the same
reason): that a sign-in attempt *outside* the cooldown actually sends a fresh
verification email. Verified manually instead, `POST /auth/login` for an
unverified account, then Mailpit's API confirms a new message arrives with
the verification link.

## Unit tests

`test_ai_tools.py` exercises the MCP and RAG proxy endpoints with Flask's
test client and stubbed servers, so it needs no running services. It covers
the disabled path, with a guard that fails on any network call, the
unavailable path, input validation, a boundary refusal, a grounded answer and
an insufficient-context reply.

`test_init_db.py` runs `student-4/db/init_db.py` against a temporary
directory. The seed runs at every container start, so it checks that a rerun
is idempotent, destination ids stay fixed, saved chats survive, chats for a
removed destination are deleted, and an older database gains the new
columns. It also checks per-country currency, coordinates, timezones, and
which cities can book flights.

`test_orchestrator.py` stubs the database and checks the AI Assistant's
replies that need no model. A city without a guide gets the list of cities
that have one, and a bare city name asks which topic.

`test_exchange_rates.py` stubs Frankfurter and student-4-db. It covers live
rates for an Australian and a Japanese city, the disabled path with a guard
that fails on any network call, a timeout and four kinds of bad response,
the cache, keeping the last good rates when a refresh fails, and the AI
Assistant quoting the same figures as the page.

`test_currency_request.py` checks AI Assistant conversions such as "How
much is 500 AUD to yen?". They are calculated in code from the stubbed
rates, with a guard that fails if the model is called. It also covers an
unsupported currency, a bare "dollars", a missing target currency and no
live rates.

`test_weather.py` stubs Open-Meteo and student-4-db. It covers current
conditions and the three day forecast, the page not waiting for the API,
month tabs that leave the live block alone, the default month in each city's
own timezone, the disabled path with a guard that fails on any network call,
a timeout and six kinds of bad response, the cache, keeping the last good
forecast, the weather code labels, and the AI Assistant quoting the same
figures as the page or being told not to describe current weather.

The workflow runs all six files before the Docker build.

```bash
python -m pip install -r student-4/tests/requirements.txt
python -m pytest -q student-4/tests/test_ai_tools.py student-4/tests/test_currency_request.py student-4/tests/test_exchange_rates.py student-4/tests/test_init_db.py student-4/tests/test_orchestrator.py student-4/tests/test_weather.py
```

Release 2 requires pre-commit `pytest` validation and post-commit AI-assisted
unit testing. Further unit tests for this feature belong in this directory.
