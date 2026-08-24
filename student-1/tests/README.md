# student-1 tests

Release 0 validates this feature through `scripts/smoke_test.py 1`, which the
`student-1` GitHub Actions workflow runs against the live services:

```bash
python3 scripts/smoke_test.py 1
```

Release 2 requires pre-commit `pytest` validation and post-commit AI-assisted
unit testing (project specification, section 7.3). Unit tests for this feature
belong in this directory.
