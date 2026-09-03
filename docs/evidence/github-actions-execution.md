# GitHub Actions workflow execution evidence - Release 0

Report section: *DevOps and CI/CD - GitHub Actions execution evidence*.
Marking criterion 6, *DevOps and GitHub Actions*.

All five workflows ran on pull request #1 and again on `main` after the
merge. Every run built that student's three microservices from a clean
GitHub-hosted runner, started them with the shared `docker-compose.yml`,
waited for `/health`, and exercised full CRUD against the live services.

These are the raw logs. Pair them with screenshots of the Actions tab -
the log text is quotable and greppable, the screenshots show the green
ticks in context.

| Workflow | Feature | Owner | Result |
|----------|---------|-------|--------|
| `student-1.yml` | Trips & Itinerary | Caroline Zhou | **success** |
| `student-2.yml` | Attractions & Dining | Kevin Kim | **success** |
| `student-3.yml` | Travel Mate | Tanishpreet Kour | **success** |
| `student-4.yml` | Account & Dashboard | Aurelia Sari | **success** |
| `student-5.yml` | Bookings & Budget | Aung Ko Khaing | **success** |

---

## student-1 - Trips & Itinerary (Caroline Zhou)

- Run: https://github.com/aurelia-sari/ads-assignment/actions/runs/32694919902
- Trigger: `pull_request`
- Commit: `0429a6c7`
- Conclusion: **success**

### Build (3 images from a clean runner)

```
 student-1-frontend  Built
 student-1-api  Built
 student-1-db  Built
```

### Byte-compile the student-1 source

```
$ python -m compileall -q student-1
(no output - step succeeded silently)
```

### Validate the shared Docker Compose configuration

```
$ docker compose config --quiet
(no output - step succeeded silently)
```

### Start the student-1 microservices

```
$ docker compose up -d \
 Network ads-assignment_travel-network  Creating
 Network ads-assignment_travel-network  Created
 Container shared-db  Creating
 Container student-1-db  Creating
 Container ai-mode  Creating
 Container shared-db  Created
 Container shared-api  Creating
 Container ai-mode  Created
 Container student-1-db  Created
 Container shared-api  Created
 Container shared-frontend  Creating
 Container student-1-api  Creating
 Container shared-frontend  Created
 Container student-1-api  Created
 Container student-1-frontend  Creating
 Container student-1-frontend  Created
 Container ai-mode  Starting
 Container shared-db  Starting
 Container student-1-db  Starting
 Container ai-mode  Started
 Container student-1-db  Started
 Container shared-db  Started
 Container shared-api  Starting
 Container shared-api  Started
 Container shared-frontend  Starting
 Container student-1-api  Starting
 Container student-1-api  Started
 Container student-1-frontend  Starting
 Container shared-frontend  Started
 Container student-1-frontend  Started
```

### Wait for the services to report healthy

```
$ python3 scripts/wait_for_health.py 5201 5101 5300
All services healthy: [5201, 5101, 5300]
```

### Validate CRUD through the database and backend APIs

```
$ python3 scripts/smoke_test.py 1
Smoke test: student-1
  ok  database service is healthy
  ok  backend/API service is healthy
  ok  GET /trips returns 200
  ok  GET /trips returns a list
  ok  /trips is seeded with at least 10 records (found 12)
  ok  POST /trips creates a record (201)
  ok  GET /trips/13 reads it back
  ok  PUT /trips/13 updates it
  ok  update actually changed status to booked
  ok  DELETE /trips/13 removes it
  ok  GET /trips/13 is 404 after delete
  ok  backend/API GET /trips returns 200
  ok  backend/API returns an HTML fragment, not JSON
  ok  shared access API serves traveller records
  ok  shared access DB is seeded (12 travellers)
  ok  trip table resolves traveller names cross-service (e.g. ['Amara Okafor'])
  ok  no trip fell back to a raw traveller id
student-1 passed all checks.
```

### Confirm the frontend microservice serves its page

```
$ curl --fail --silent --show-error http://localhost:8081 > /dev/null
(no output - step succeeded silently)
```

---

## student-2 - Attractions & Dining (Kevin Kim)

- Run: https://github.com/aurelia-sari/ads-assignment/actions/runs/32694919921
- Trigger: `pull_request`
- Commit: `0429a6c7`
- Conclusion: **success**

### Build (3 images from a clean runner)

```
 student-2-frontend  Built
 student-2-api  Built
 student-2-db  Built
```

### Byte-compile the student-2 source

```
$ python -m compileall -q student-2
(no output - step succeeded silently)
```

### Validate the shared Docker Compose configuration

```
$ docker compose config --quiet
(no output - step succeeded silently)
```

### Start the student-2 microservices

```
$ docker compose up -d \
 Network ads-assignment_travel-network  Creating
 Network ads-assignment_travel-network  Created
 Container student-2-db  Creating
 Container ai-mode  Creating
 Container shared-db  Creating
 Container ai-mode  Created
 Container student-2-db  Created
 Container student-2-api  Creating
 Container shared-db  Created
 Container shared-api  Creating
 Container student-2-api  Created
 Container student-2-frontend  Creating
 Container shared-api  Created
 Container shared-frontend  Creating
 Container shared-frontend  Created
 Container student-2-frontend  Created
 Container shared-db  Starting
 Container student-2-db  Starting
 Container ai-mode  Starting
 Container ai-mode  Started
 Container shared-db  Started
 Container shared-api  Starting
 Container student-2-db  Started
 Container student-2-api  Starting
 Container shared-api  Started
 Container shared-frontend  Starting
 Container student-2-api  Started
 Container student-2-frontend  Starting
 Container shared-frontend  Started
 Container student-2-frontend  Started
```

### Wait for the services to report healthy

```
$ python3 scripts/wait_for_health.py 5202 5102 5300
All services healthy: [5202, 5102, 5300]
```

### Validate CRUD through the database and backend APIs

```
$ python3 scripts/smoke_test.py 2
Smoke test: student-2
  ok  database service is healthy
  ok  backend/API service is healthy
  ok  GET /records returns 200
  ok  GET /records returns a list
  ok  /records is seeded with at least 10 records (found 12)
  ok  POST /records creates a record (201)
  ok  GET /records/13 reads it back
  ok  PUT /records/13 updates it
  ok  update actually changed category to smoke-updated
  ok  DELETE /records/13 removes it
  ok  GET /records/13 is 404 after delete
  ok  backend/API GET /records returns 200
  ok  backend/API returns an HTML fragment, not JSON
student-2 passed all checks.
```

### Confirm the frontend microservice serves its page

```
$ curl --fail --silent --show-error http://localhost:8082 > /dev/null
(no output - step succeeded silently)
```

---

## student-3 - Travel Mate (Tanishpreet Kour)

- Run: https://github.com/aurelia-sari/ads-assignment/actions/runs/32694919952
- Trigger: `pull_request`
- Commit: `0429a6c7`
- Conclusion: **success**

### Build (3 images from a clean runner)

```
 student-3-frontend  Built
 student-3-api  Built
 student-3-db  Built
```

### Byte-compile the student-3 source

```
$ python -m compileall -q student-3
(no output - step succeeded silently)
```

### Validate the shared Docker Compose configuration

```
$ docker compose config --quiet
(no output - step succeeded silently)
```

### Start the student-3 microservices

```
$ docker compose up -d \
 Network ads-assignment_travel-network  Creating
 Network ads-assignment_travel-network  Created
 Container shared-db  Creating
 Container student-3-db  Creating
 Container ai-mode  Creating
 Container ai-mode  Created
 Container shared-db  Created
 Container shared-api  Creating
 Container student-3-db  Created
 Container student-3-api  Creating
 Container shared-api  Created
 Container shared-frontend  Creating
 Container student-3-api  Created
 Container student-3-frontend  Creating
 Container shared-frontend  Created
 Container student-3-frontend  Created
 Container ai-mode  Starting
 Container shared-db  Starting
 Container student-3-db  Starting
 Container student-3-db  Started
 Container shared-db  Started
 Container shared-api  Starting
 Container ai-mode  Started
 Container student-3-api  Starting
 Container student-3-api  Started
 Container student-3-frontend  Starting
 Container shared-api  Started
 Container shared-frontend  Starting
 Container student-3-frontend  Started
 Container shared-frontend  Started
```

### Wait for the services to report healthy

```
$ python3 scripts/wait_for_health.py 5203 5103 5300
All services healthy: [5203, 5103, 5300]
```

### Validate CRUD through the database and backend APIs

```
$ python3 scripts/smoke_test.py 3
Smoke test: student-3
  ok  database service is healthy
  ok  backend/API service is healthy
  ok  GET /records returns 200
  ok  GET /records returns a list
  ok  /records is seeded with at least 10 records (found 12)
  ok  POST /records creates a record (201)
  ok  GET /records/13 reads it back
  ok  PUT /records/13 updates it
  ok  update actually changed category to smoke-updated
  ok  DELETE /records/13 removes it
  ok  GET /records/13 is 404 after delete
  ok  backend/API GET /records returns 200
  ok  backend/API returns an HTML fragment, not JSON
student-3 passed all checks.
```

### Confirm the frontend microservice serves its page

```
$ curl --fail --silent --show-error http://localhost:8083 > /dev/null
(no output - step succeeded silently)
```

---

## student-4 - Account & Dashboard (Aurelia Sari)

- Run: https://github.com/aurelia-sari/ads-assignment/actions/runs/32694919887
- Trigger: `pull_request`
- Commit: `0429a6c7`
- Conclusion: **success**

### Build (3 images from a clean runner)

```
 student-4-frontend  Built
 student-4-api  Built
 student-4-db  Built
```

### Byte-compile the student-4 source

```
$ python -m compileall -q student-4
(no output - step succeeded silently)
```

### Validate the shared Docker Compose configuration

```
$ docker compose config --quiet
(no output - step succeeded silently)
```

### Start the student-4 microservices

```
$ docker compose up -d \
 Network ads-assignment_travel-network  Creating
 Network ads-assignment_travel-network  Created
 Container student-4-db  Creating
 Container shared-db  Creating
 Container ai-mode  Creating
 Container shared-db  Created
 Container shared-api  Creating
 Container student-4-db  Created
 Container ai-mode  Created
 Container student-4-api  Creating
 Container shared-api  Created
 Container shared-frontend  Creating
 Container student-4-api  Created
 Container student-4-frontend  Creating
 Container shared-frontend  Created
 Container student-4-frontend  Created
 Container student-4-db  Starting
 Container ai-mode  Starting
 Container shared-db  Starting
 Container shared-db  Started
 Container ai-mode  Started
 Container shared-api  Starting
 Container student-4-db  Started
 Container student-4-api  Starting
 Container student-4-api  Started
 Container student-4-frontend  Starting
 Container shared-api  Started
 Container shared-frontend  Starting
 Container student-4-frontend  Started
 Container shared-frontend  Started
```

### Wait for the services to report healthy

```
$ python3 scripts/wait_for_health.py 5204 5104 5300
All services healthy: [5204, 5104, 5300]
```

### Validate CRUD through the database and backend APIs

```
$ python3 scripts/smoke_test.py 4
Smoke test: student-4 sign-up, email verification & sign-in
  ok  GET /health returns 200
  ok  GET /guides returns 200
  ok  seeded destination Sydney is present
  ok  seeded destination Melbourne is present
  ok  seeded destination Perth is present
  ok  seeded destination Hobart is present
  ok  GET /guides?query=Sydney returns 200
  ok  searching by city returns a match
  ok  searching by city excludes other cities
  ok  the Sydney row links to its guide detail endpoint
  ok  GET /guides/1 returns 200
  ok  the detail view names the city
  ok  the detail view has a back-to-list link
  ok  the detail view has a Currency subheading
  ok  the detail view names the Australian Dollar code
  ok  currency copy uses a period, not a semicolon, between sentences
  ok  guide text does not use an em dash
  ok  the detail view has a Transportation subheading
  ok  the detail view lists a Flights transport tab
  ok  the default (flights) transport tab shows a booking button
  ok  the flights booking button links to student-5's search
  ok  GET /guides/<id>/transportation?type=metro returns 200
  ok  the metro tab is shown
  ok  the metro tab does not show a flights booking button
  ok  the detail view has a Visa subheading
  ok  the detail view lists a New Zealand visa tab
  ok  no nationality is picked by default, so a placeholder is shown instead of a guess
  ok  GET /guides/<id>/visa?nationality=New Zealand returns 200
  ok  New Zealand's requirement type is shown
  ok  picking a nationality replaces the placeholder with its requirement
  ok  GET /guides/<id>/visa?nationality=<unknown> returns 200
  ok  an unseeded nationality falls back to the placeholder, not an error
  ok  the detail view has a Weather subheading
  ok  the detail view lists a January weather tab
  ok  the default weather tab shows a temperature
  ok  GET /guides/<id>/weather?month=July returns 200
  ok  the July tab is shown
  ok  GET /guides/<id>/weather?month=<invalid> returns 200
  ok  an invalid month falls back to a real month, not an error
  ok  GET /guides?query=Cairns returns 200
  ok  the Cairns row links to its guide detail endpoint
  ok  GET /guides/7/weather?month=January returns 200
  ok  Cairns's best time to visit note names the dry season
  ok  the detail view has a Safety subheading
  ok  the detail view shows Australia's safety level
  ok  the detail view shows Sydney's own safety tips
  ok  GET /guides/1/safety returns 200
  ok  the safety fragment has a Safety subheading
  ok  GET /guides/7/safety returns 200
  ok  Cairns has its own safety tips, not Sydney's
  ok  GET /guides/<unknown id>/safety still returns 200
  ok  an unknown destination id shows a not-found message, not an error
  ok  GET /guides?query=Alice Springs returns 200
  ok  the Alice Springs row links to its guide detail endpoint
  ok  GET /guides/13 returns 200
  ok  Alice Springs has no metro, so no Metro tab is shown
  ok  Alice Springs has no train service, so no Train tab is shown
  ok  GET /guides/<unknown id> returns 404
  ok  GET /guides/1/currency returns 200
  ok  currency fragment has a Currency subheading
  ok  currency fragment names the Australian Dollar code
  ok  GET /guides/<unknown id>/currency still returns 200
  ok  an unknown destination id shows a not-found message, not an error
  ok  GET /guides?query=Australia returns 200
  ok  searching by country returns its cities
  ok  GET /guides?query=Nowhereville returns 200
  ok  an unmatched search shows the not-found placeholder
  ok  seeded student1 can sign in
  ok  seeded traveller6 is pending verification
  ok  POST /auth/register without terms_accepted returns 400
  ok  error message names the T&C requirement
  ok  POST /auth/register with a weak password returns 400
  ok  POST /auth/register with an invalid email returns 400
  ok  POST /auth/register with valid data returns 201
  ok  created account has the requested email
  ok  created account starts unverified
  ok  the response never leaks the token or the password hash
  ok  registering the same email again returns 409
  ok  verification email arrives in Mailpit with a link
  ok  visiting the verification link returns 200
  ok  the link confirms verification
  ok  reusing the same (now-spent) link returns 404
  ok  resending for an already-verified account returns 400
  ok  second account for resend testing registers successfully
  ok  resending within 60s of registering returns 429
  ok  429 response names how long to wait
  ok  POST /auth/login with the wrong password returns 401
  ok  wrong-password error message is the generic one
  ok  POST /auth/login for an email with no account returns 401
  ok  unknown-email error is identical to wrong-password (no account enumeration)
  ok  POST /auth/login with the correct password on an unverified account returns 403
  ok  403 response names the email_not_verified error code
  ok  signing in to an unverified account within the resend cooldown does not send a duplicate email
  ok  POST /auth/login with the correct password on a verified account returns 200
  ok  login response returns the signed-in user
  ok  login response never leaks the password hash or verification token
  ok  GET /auth/status/<id> returns 200
  ok  session is valid right after login
  ok  no last_logout recorded yet
  ok  POST /auth/logout without a user_id returns 400
  ok  POST /auth/logout for the signed-in user returns 200
  ok  logout response reports in_session = 0
  ok  logout response stamps sign_out_at
  ok  GET /auth/status/<id> returns 200 after logout
  ok  session is invalid after logout
  ok  last_logout is now recorded
  ok  logging out again with no open session returns 404
  ok  GET /auth/status/<id> for an unknown id still returns 200
  ok  an unknown user id is reported as not signed in, not an error
  ok  student-4 landing page (index.html) is served
  ok  landing page calls verifySession before showing its content
  ok  signin.html is served without a session
  ok  signup.html is served without a session
  ok  verify-pending.html is served without a session
  ok  logout.html is served (not just index.html's fallback)
  ok  logout.html gates its content behind the one-time sign-out flag
  ok  shared home page is served
  ok  shared home page loads the shared session guard

student-4 sign-up, email verification & sign-in passed all checks.
```

### Confirm the frontend microservice serves its page

```
$ curl --fail --silent --show-error http://localhost:8084 > /dev/null
(no output - step succeeded silently)
```

---

## student-5 - Bookings & Budget (Aung Ko Khaing)

- Run: https://github.com/aurelia-sari/ads-assignment/actions/runs/32694920001
- Trigger: `pull_request`
- Commit: `0429a6c7`
- Conclusion: **success**

### Build (3 images from a clean runner)

```
 student-5-db  Built
 student-5-frontend  Built
 student-5-api  Built
```

### Byte-compile the student-5 source

```
$ python -m compileall -q student-5
(no output - step succeeded silently)
```

### Validate the shared Docker Compose configuration

```
$ docker compose config --quiet
(no output - step succeeded silently)
```

### Start the student-5 microservices

```
$ docker compose up -d \
 Network ads-assignment_travel-network  Creating
 Network ads-assignment_travel-network  Created
 Container student-5-db  Creating
 Container shared-db  Creating
 Container ai-mode  Creating
 Container ai-mode  Created
 Container student-5-db  Created
 Container student-5-api  Creating
 Container shared-db  Created
 Container shared-api  Creating
 Container student-5-api  Created
 Container shared-api  Created
 Container shared-frontend  Creating
 Container student-5-frontend  Creating
 Container student-5-frontend  Created
 Container shared-frontend  Created
 Container student-5-db  Starting
 Container shared-db  Starting
 Container ai-mode  Starting
 Container student-5-db  Started
 Container shared-db  Started
 Container shared-api  Starting
 Container ai-mode  Started
 Container student-5-api  Starting
 Container shared-api  Started
 Container shared-frontend  Starting
 Container student-5-api  Started
 Container student-5-frontend  Starting
 Container shared-frontend  Started
 Container student-5-frontend  Started
```

### Wait for the services to report healthy

```
$ python3 scripts/wait_for_health.py 5205 5105 5300
All services healthy: [5205, 5105, 5300]
```

### Validate CRUD through the database and backend APIs

```
$ python3 scripts/smoke_test.py 5
Smoke test: student-5
  ok  database service is healthy
  ok  backend/API service is healthy
  ok  GET /records returns 200
  ok  GET /records returns a list
  ok  /records is seeded with at least 10 records (found 12)
  ok  POST /records creates a record (201)
  ok  GET /records/13 reads it back
  ok  PUT /records/13 updates it
  ok  update actually changed category to smoke-updated
  ok  DELETE /records/13 removes it
  ok  GET /records/13 is 404 after delete
  ok  backend/API GET /records returns 200
  ok  backend/API returns an HTML fragment, not JSON
student-5 passed all checks.
```

### Confirm the frontend microservice serves its page

```
$ curl --fail --silent --show-error http://localhost:8085 > /dev/null
(no output - step succeeded silently)
```

---

Workflow definitions are in `.github/workflows/`. The validation script is `scripts/smoke_test.py`, runnable locally as `python3 scripts/smoke_test.py N`.
