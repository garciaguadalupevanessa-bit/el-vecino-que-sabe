#!/usr/bin/env bash
# Checks that your machine is ready to work on El Vecino que Sabe.
#
# Usage:  ./scripts/doctor.sh            (before starting the stack)
#         ./scripts/doctor.sh --up       (with the stack running: checks the URLs)
# On Windows, run it from Git Bash or WSL.

set -u
UP=0
[ "${1:-}" = "--up" ] && UP=1

ok=0; failures=0; warnings=0
pass() { echo "  ✅ $1"; ok=$((ok + 1)); }
fail() { echo "  ❌ $1"; failures=$((failures + 1)); }
warn() { echo "  ⚠️  $1"; warnings=$((warnings + 1)); }

# Returns 0 if the port is in use, 1 if it is free and 2 if it cannot be checked
port_in_use() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -qE "[:.]${p}[[:space:]]"; return $(( $? == 0 ? 0 : 1 ))
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; return $(( $? == 0 ? 0 : 1 ))
  fi
  return 2
}

echo "== Tools"
if command -v git >/dev/null 2>&1; then pass "git $(git --version | awk '{print $3}')"; else fail "git is not installed"; fi

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then pass "Docker is running"; else fail "Docker is installed but not responding (is Docker Desktop started?)"; fi
  if docker compose version >/dev/null 2>&1; then pass "docker compose $(docker compose version --short 2>/dev/null)"; else fail "'docker compose' (v2) is missing"; fi
else
  fail "Docker is not installed"
fi

if command -v node >/dev/null 2>&1; then
  major=$(node -v | sed 's/^v\([0-9]*\).*/\1/')
  if [ "${major:-0}" -ge 18 ]; then pass "node $(node -v)"; else warn "node $(node -v): version 18 or newer is needed for the frontend tests"; fi
else
  warn "node is not installed (only needed to develop the frontend outside Docker)"
fi

if command -v python3 >/dev/null 2>&1; then pass "python3 $(python3 --version | awk '{print $2}')"; else warn "python3 is not installed (only needed to run scripts/explore_sources.py outside Docker)"; fi

echo "== Configuration"
if [ -f .env ]; then
  pass ".env exists"
  key=$(grep -E '^LLM_API_KEY=' .env | head -1 | cut -d= -f2-)
  if [ -n "$key" ]; then pass "LLM_API_KEY is filled in"; else fail "LLM_API_KEY is empty in .env"; fi
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git check-ignore -q .env; then pass ".env is ignored by Git"; else fail ".env is NOT ignored by Git: do not commit it"; fi
  else
    warn "this is not a Git repository yet"
  fi
else
  fail ".env does not exist: run  cp .env.example .env  and fill in LLM_API_KEY"
fi

if [ "$UP" -eq 0 ]; then
  echo "== Free ports (3000 frontend, 8000 API, 5432 Postgres)"
  for p in 3000 8000 5432; do
    port_in_use "$p"; state=$?
    if [ "$state" -eq 0 ]; then fail "port $p is already in use: close it or change the port in docker-compose.yml"
    elif [ "$state" -eq 1 ]; then pass "port $p is free"
    else warn "cannot check port $p on this system (if it is taken, Docker will tell you on startup)"; fi
  done
else
  echo "== Running stack"
  if ! command -v curl >/dev/null 2>&1; then
    fail "curl is not installed"
  else
    health=$(curl -fsS --max-time 10 http://localhost:8000/api/health 2>/dev/null || true)
    if [ -z "$health" ]; then fail "the API does not respond at http://localhost:8000/api/health"
    else
      pass "the API responds: $health"
      case "$health" in *'"data_source":"postgres"'*) pass "data comes from Postgres";; *) fail "data does NOT come from Postgres";; esac
      case "$health" in *'"llm_configured":true'*) pass "the LLM key is configured";; *) fail "the backend does not see LLM_API_KEY";; esac
    fi
    if curl -fsS --max-time 10 http://localhost:3000/ >/dev/null 2>&1; then pass "the frontend responds at http://localhost:3000"; else fail "the frontend does not respond at http://localhost:3000"; fi
    if curl -fsS --max-time 10 http://localhost:3000/api/health >/dev/null 2>&1; then pass "nginx forwards /api to the backend"; else fail "nginx does not forward /api to the backend"; fi
  fi
fi

echo
echo "Result: $ok passed, $warnings warnings, $failures failures"
[ "$failures" -eq 0 ]
