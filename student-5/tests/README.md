# student-5 tests

Release 0 validates this feature through `scripts/smoke_test.py 5`, which the
`student-5` GitHub Actions workflow runs against the live services:

```bash
python3 scripts/smoke_test.py 5
```

Release 2 requires pre-commit `pytest` validation and post-commit AI-assisted
unit testing (project specification, section 7.3). Unit tests for this feature
belong in this directory.
