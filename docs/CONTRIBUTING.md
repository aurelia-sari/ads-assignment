# Working in this repository - Group 25

## Branching

`main` is the integration branch and is what the tutor marks. Never commit to
it directly.

```bash
git checkout main && git pull
git checkout -b student-N/<short-feature-name>
# ... work ...
git push -u origin student-N/<short-feature-name>
```

Open a pull request into `main`. Your `student-N` workflow runs on the pull
request; merge only when it is green.

## Staying out of each other's way

| You own | You edit |
|---------|----------|
| Your feature | `student-N/**` and `.github/workflows/student-N.yml` |
| Nobody's alone | `docker-compose.yml`, `shared/**`, `ai-services/**` |

In `docker-compose.yml` only touch your own three service blocks. If two people
need to change the shared files, agree in the group chat first - that file is
where merge conflicts will happen.

## Before you open a pull request

```bash
docker compose up --build -d
python3 scripts/smoke_test.py N     # your number
./scripts/dev.sh health             # nothing else broke
```

## Definition of done for a Release 0 feature

- [ ] Database service owns its own schema, seeded with 10+ rows per table
- [ ] Full CRUD: create, read, update, delete, all reachable from the page
- [ ] Backend/API reaches the database only over HTTP, never the SQLite file
- [ ] AI feature calls `ai-mode`, never Ollama directly
- [ ] Any data you do not own is read over HTTP from the owning service, and
      your page still renders when that service is down
- [ ] Page links `/shared/css/theme.css` and no other stylesheet
- [ ] Feature reachable from the unified home page at <http://localhost:8080>
- [ ] `scripts/smoke_test.py N` passes
- [ ] Your GitHub Actions workflow is green
- [ ] Your sections of `docs/technical-report.md` are filled in

The last two matter as much as the code. The specification is explicit that a
feature which is not integrated into the group application scores zero, and the
individual report sections are marked per student.

## Reading another feature's data

You will need data you do not own - a trip, a traveller, an attraction. The rule
is that you call the owning service's API. You never open another service's
SQLite file, and you never add a column that copies data another feature owns.

`student-1/api/services/shared_api.py` is the worked example. Copy its three
properties:

1. **Fetch once and index**, rather than one request per row.
2. **Cache briefly** if the data is re-read on every render. 30 seconds is
   plenty and avoids cross-service invalidation.
3. **Degrade, never fail.** If the other service is down, render what you have.
   A trip row shows `#7` instead of a name; it does not 503.

Point 3 decides whether the Week 6 demo survives one slow container.

Ownership boundary for traveller data, from ADR-001: `shared-db` owns identity
(name, email, home city). student-4 owns profile (preferences, onboarding,
dashboard). `traveller_id` is the join key and the only traveller field you may
store in your own tables.

## Evidence to collect as you go

Do not leave this to the last week - most of it can only be captured while
something is running.

- Screenshots of your feature working in the integrated application
- A green GitHub Actions run for your workflow
- `docker compose ps` with everything up
- An agentic loop run record from `ai-services/agentic-loop/runs/`
- Your commit log and contribution notes
- Attendance checkpoints

Put files in `docs/evidence/` and reference them from the report.
