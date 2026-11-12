# Phase 7 — Validation commands (PowerShell)

Run from the project root. These checks do not import new BDNS data.

## Backend unit suite

```powershell
docker compose run --rm --no-deps --build backend pytest -q
```

## PostgreSQL integration suite

Use a dedicated disposable database; the database tests clear their tables. Do not point `$testDbUrl` at the application's working database. If the dedicated test database used earlier is still available:

```powershell
docker compose exec -e "TEST_DATABASE_URL=$testDbUrl" backend pytest -q tests/test_db.py
```

Expected: 9 passed. If the variable is not set, create a separate test database and set its URL before running this command.

## Frontend tests and production build

```powershell
docker compose exec frontend npm test
docker compose up -d --build frontend
```

The second command rebuilds the production frontend image; a successful build is the bundle check.

## Full-stack smoke test

```powershell
docker compose up -d --build --wait --wait-timeout 180
Invoke-RestMethod http://localhost:8000/api/health
(Invoke-WebRequest http://localhost:3000/).Content | Select-String "El Vecino que Sabe"
Invoke-RestMethod http://localhost:3000/api/health
```

Health should report `status = ok` and `data_source = postgres`. The frontend page should contain the app name, and its `/api/health` route should reach the backend.

## Manual agricultural-sector review

With the app running, review crop-only, livestock and mixed profiles, including one national and one territorial query. Check that the response is understandable without administrative jargon, keyboard navigation reaches the result and source links, focus is visible, and the screen reader can identify result headings, requirement states and link names. Record confusing wording or inaccessible controls as release blockers. This review needs people from the agricultural sector and cannot be signed off by automated checks.

CI runs all backend unit tests, PostgreSQL integration tests, frontend tests/build, and Docker Compose smoke checks on pull requests. The last human review remains a release gate.
