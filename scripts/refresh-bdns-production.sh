#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$repo_root/.env.production"
log_dir="${BDNS_REFRESH_LOG_DIR:-$repo_root/logs}"

if [[ ! -f "$env_file" ]]; then
  echo "Missing $env_file; configure the production database URL first." >&2
  exit 2
fi
command -v docker >/dev/null || { echo "Docker is required." >&2; exit 2; }
mkdir -p "$log_dir"
log_file="$log_dir/bdns-refresh-$(date -u +%Y-%m).log"

compose=(docker compose --project-directory "$repo_root" --env-file "$env_file" -f "$repo_root/compose.production.yaml")
args=(python -m app.bdns.importer --regions 21 --administration-types A --terms "agricultura,ganadería" --max-pages 1 --page-size 10)
if [[ "${BDNS_DRY_RUN:-false}" == "true" ]]; then
  args+=(--dry-run)
fi

{
  printf '\n[%s] Starting bounded Aragón BDNS refresh (dry-run=%s)\n' "$(date -u +%FT%TZ)" "${BDNS_DRY_RUN:-false}"
  "${compose[@]}" run --rm --no-deps backend "${args[@]}"
  printf '[%s] BDNS refresh finished successfully\n' "$(date -u +%FT%TZ)"
} 2>&1 | tee -a "$log_file"
