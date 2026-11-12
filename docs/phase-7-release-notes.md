# Phase 7 — Release readiness notes

## Automated validation

Validated by the user in Docker on 2026-11-11:

- Backend: **115 passed, 9 skipped**. The skipped cases are PostgreSQL integration cases that require `TEST_DATABASE_URL`.
- PostgreSQL integration: **9 passed** against the dedicated `elvecinoquesabe_phase5_test` database.
- Frontend: **13 passed**.
- Production build: backend and frontend images built successfully.
- Full-stack smoke: Compose services became healthy; `/api/health` returned `status=ok` and `data_source=postgres`; the frontend page and proxied health endpoint responded.

The backend run emitted the known non-blocking pytest cache permission warning for `/app/.pytest_cache`; all executed tests passed. The PowerShell `Invoke-WebRequest` page check displayed its standard parsing confirmation, and the user continued successfully.

## Coverage and release limitations

- Search coverage is incomplete. A candidate list or an empty result is not proof that all calls in a territory or campaign were found.
- Campaign status, deadlines, and source documents can change. Only verified, explicitly recorded information is used for definitive aid requirements; an old or absent campaign record remains uncertain.
- An expired ISO deadline suppresses an otherwise-open verified aid from `only_open` search. Unknown and non-ISO deadline formats are not interpreted.
- Automated scenarios are not a legal determination of eligibility; the administration decides each application.
- Language clarity and accessibility still need a short review with people from the agricultural sector. Automated checks and the Docker smoke test do not replace that review.
