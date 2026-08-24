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
Smoke test: student-4
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
student-4 passed all checks.
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
