# student-2 tests

Release 0 validates this feature through `scripts/smoke_test.py 2`, which the
`student-2` GitHub Actions workflow runs against the live services:

```bash
python3 scripts/smoke_test.py 2
```

That shared script still checks the generic `/records` scaffold (per-student
resources are opted in via its `RESOURCES` dict, and student-2 hasn't been
added there). The real `places`/`favourites` CRUD and validation behaviour is
covered instead by `smoke_test.py` in this directory:

```bash
docker compose up -d student-2-db student-2-api

# needs `requests`; this repo's Homebrew Python blocks a bare `pip install`
# (PEP 668), so use a virtual environment:
cd student-2/tests
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 smoke_test.py
```

Already have `student-2/agentic-loop/.venv` set up? It has `requests`
installed too, so `source ../agentic-loop/.venv/bin/activate` works just as
well - no need for a second virtual environment.

It is a plain, deterministic pass/fail test - no LLM involved - and is not
yet wired into CI. `student-2/agentic-loop/` runs it and layers an Ollama
review on top of the result.

Release 2 requires pre-commit `pytest` validation and post-commit AI-assisted
unit testing (project specification, section 7.3). Unit tests for this feature
belong in this directory.
