# Phase 8 — Deployment and operations runbook

This repository now includes a production Compose template for a single application host with an external managed PostgreSQL database. No cloud/provider account has been selected or deployed from this workspace. Provider-side networking, secrets, TLS, backups and alerting must be configured before public launch.

The production Compose file declares its own project name, `elvecinoquesabe-prod`, so its containers and document volume are isolated from the local development project. Keep using this file for every production Compose command; do not use `--remove-orphans` to silence warnings from another Compose project. If you test the production frontend on a machine where port 3000 is already occupied, set `FRONTEND_PORT` in `.env.production` to an unused port.

## Deployment prerequisites

1. Select a host that can run Docker Compose and a managed PostgreSQL service in a compatible network region.
2. Create a production database and an application database role. Restrict database ingress to the application host, require TLS, and use the provider's `sslmode=require` connection string. URL-encode reserved characters in database credentials. Do not use the development database or development passwords.
3. Copy `.env.production.example` to `.env.production` on the host. Fill `DATABASE_URL`, `LLM_API_KEY`, and a long random `BDNS_REVIEW_TOKEN`. Keep the file out of source control and restrict access to the deployment account. Prefer the host's secret manager when available.
4. Put a TLS reverse proxy or provider HTTPS ingress in front of the frontend. The Compose template binds the frontend to `127.0.0.1:3000`; the API is available only on the internal Compose network. Do not publish PostgreSQL or port 8000 to the public internet.

## Build, deploy and rollback

Run from the deployed project directory after configuring DNS/TLS and the managed database:

```bash
docker compose --env-file .env.production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.production.yaml up -d --build --wait --wait-timeout 180
curl -fsS http://127.0.0.1:3000/api/health
curl -fsS http://127.0.0.1:3000/ | grep -q "El Vecino que Sabe"
```

The health response must report `status=ok` and `data_source=postgres`. Apply a tested release by recording the current image tag, updating the code, rebuilding, and running the same smoke checks. For rollback, redeploy the previous image/code version; do not restore an old database snapshot unless the incident requires data recovery and the owner approves it. Schema migrations run during application schema initialization; back up the database before releases that change schema.

The frontend container is the only published service, bound to loopback for a same-host TLS proxy. If the chosen platform requires direct service ingress instead of a same-host proxy, adapt the ingress rules while keeping the API private and HTTPS enforced.

## Database and document backups

Configure backups in the managed database provider, not in the application container. Suggested initial policy for review: daily automated backups, 30-day retention, point-in-time recovery when offered, and a restore rehearsal every quarter into a separate staging database. Confirm the retention and recovery objectives with the service owner before launch.

The separate `bdns_documents` Compose volume stores downloaded official PDFs. Back it up as well, or move it to a managed encrypted object store before running multiple backend replicas. A database backup alone does not contain this volume. Encrypt backups at rest and restrict restore access. Record the last successful backup, restore test and responsible operator in the service log.

Never test restore by overwriting production. Restore into a fresh staging database and a separate document volume, verify the health endpoint and sample records, then remove the staging copy according to the retention policy.

## BDNS refresh schedule

Refresh cadence proposal: monthly, beginning with the existing Aragón autonomous-administration slice only (`--regions 21 --administration-types A`). Before enabling the schedule, run a dry run and inspect the candidates. The refresh script uses one page of ten records for each of `agricultura` and `ganadería`, limits calls through the existing BDNS client pacing/retry settings, and imports metadata only; it does not verify eligibility rules.

```bash
BDNS_DRY_RUN=true ./scripts/refresh-bdns-production.sh
./scripts/refresh-bdns-production.sh
```

Run the first command and review its output. Run the second only after the preview is acceptable. On a Linux deployment host, a monthly cron entry can call the import script at 04:15 UTC on the first day of the month:

```cron
15 4 1 * * /bin/bash /opt/elvecinoquesabe/scripts/refresh-bdns-production.sh
```

Install the cron entry only after confirming the actual project path and completing a successful manual dry run/import. Review `logs/bdns-refresh-YYYY-MM.log` after each run and configure log rotation/retention. Keep the query bound fixed until measured recall and reviewer capacity justify an increase.

## Monitoring and service checks

- Configure an external HTTPS uptime check for the public application URL and alert on non-200 responses or sustained downtime.
- Check `GET /api/health` from the host or a trusted monitor. Alert if `status` is not `ok`, `data_source` is not `postgres`, or `llm_configured` is false.
- Inspect container health, restart counts, disk use for the database and PDF volume, and backend/frontend logs at least weekly.
- After every scheduled import, record success/failure, mapped call count, and coverage observations. Review import errors, stale source/extraction warnings and the protected `/review` queue weekly during active campaigns and monthly otherwise.
- The health endpoint is a liveness/data-origin check, not a complete provider or LLM availability test. Periodically send a test chat query from a controlled account and verify source links.
- Do not put API keys, database URLs or bearer tokens in logs, screenshots, monitoring labels or issue reports.

## Coverage status and corrections

Publish the maintained [`service-status-template.md`](service-status-template.md) at the same location as the public app. Update its last-updated date after each successful import/review cycle. State explicitly that current discovery is bounded to Aragón and the recorded terms/page limits, that the aid catalog is incomplete, and that missing results do not prove no aid exists.

Until a public contact channel is selected, do not advertise an unmonitored correction address. Before public launch, set a monitored email/form/issue channel and publish it with the service status. Use [`correction-process.md`](correction-process.md) to record each correction, source evidence, review decision and response without collecting unnecessary personal data.

## Operational ownership

Assign named people before launch; these are roles, not currently assigned individuals:

| Role | Responsibilities | Assigned person/contact |
|---|---|---|
| Service owner | Release decisions, public status and correction responses | Pending |
| Data/source reviewer | BDNS refreshes, campaign/source checks, review queue and quality findings | Pending |
| Infrastructure operator | Hosting, secrets, backups/restores, monitoring and incident response | Pending |

Keep this table current and ensure every operational alert and correction request reaches an active owner.
