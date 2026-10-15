# student-1 tests

## Post-commit endpoint tests (Release 2, criterion 4)

`test_endpoints.py` tests two endpoint functions of `student-1-api` against
the running containers. The `student-1` GitHub Actions workflow runs them after
every push, once the services report healthy.

| Endpoint function | Route | What is checked |
|---|---|---|
| `create_trip` | `POST /trips` | the trip reaches student-1-db with its fields intact and the refreshed table includes it; an end date before the start date and missing fields are rejected with 400 and nothing is stored |
| `list_trip_days` | `GET /trips/<id>/days` | the trip's days render in order with an add-day form scoped to that trip; a trip with no days says so; days from other trips never appear |

Each test creates its own uniquely named trip and deletes it afterwards, so
the seed data is never touched.

Locally, with the stack up (`./scripts/dev.sh up`):

```bash
python -m pip install -r student-1/tests/requirements.txt
python -m pytest -v student-1/tests/test_endpoints.py
```

In CI the results are written to `reports/student-1-endpoint-tests.xml`,
uploaded as the `student-1-endpoint-tests` artifact, and summarised on the
workflow run page.

## CRUD smoke test

`scripts/smoke_test.py 1` validates CRUD through the database and backend APIs
and runs in the same workflow:

```bash
python3 scripts/smoke_test.py 1
```
