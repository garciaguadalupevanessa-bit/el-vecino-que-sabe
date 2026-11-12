# Phase 8 — Validation checklist

Run the preparation checks from the project root in PowerShell. These commands validate configuration and the bounded import preview; they do not deploy publicly or write BDNS data.

## 1. Prepare a local production environment file

```powershell
if (-not (Test-Path .env.production)) { Copy-Item .env.production.example .env.production }
```

For configuration checks, the example values are enough. Do not deploy until `DATABASE_URL` points to the selected managed database, TLS is required, and all real secrets have been entered through the host's secret manager or protected environment file.

## 2. Check production Compose configuration

```powershell
docker compose --env-file .env.production -f compose.production.yaml config --quiet
```

No output and exit code 0 means the Compose file and environment file parse successfully. This does not establish a database connection.

## 3. Preview the bounded production refresh

```powershell
docker compose --env-file .env.production -f compose.production.yaml run --rm --no-deps backend python -m app.bdns.importer --regions 21 --administration-types A --terms "agricultura,ganadería" --max-pages 1 --page-size 10 --dry-run
```

The result should say `dry run, no database writes` and show a bounded preview. If BDNS is temporarily unavailable, retry later; do not remove the page/size limits to make the check pass.

## 4. Check scheduled-runner shell syntax (on Bash / Linux)

```bash
bash -n scripts/refresh-bdns-production.sh
```

Before the first real scheduled import, set up the managed DB, run and review the dry run, then manually execute `scripts/refresh-bdns-production.sh` once. Confirm its log says the refresh finished successfully before adding the monthly cron entry in the operations runbook.

## 5. Provider-side checks before launch

These cannot be validated from the repository alone. Confirm and record: public host and TLS URL; restricted network access to the managed database with TLS; provider-managed backup retention and a successful restore into staging; external uptime alert delivery; persistent PDF storage backup; a working correction contact; named service/data/infrastructure owners; and the public service status page. Only then deploy using the production runbook.

## Validation record

The user validated the production Compose configuration and bounded BDNS dry run on 2026-11-11. Compose configuration passed; the dry run built the backend image, mapped 11 unique calls across 2 bounded region/term queries, and confirmed that it made no database writes. After the production template declared the isolated `elvecinoquesabe-prod` project name, the user repeated the check: no orphan-container warning appeared. Compose created the separate production network and `bdns_documents` volume for future use. Provider-side launch checks remain pending.
