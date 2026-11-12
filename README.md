# El Vecino que Sabe (ELVECINOQUESABE)

An AI agent that helps agricultural, livestock and mixed farms in Spain find out **which public aid they can apply for**, which requirements they meet and which they are missing, **how to apply**, and what **alternatives** they have.

Project for the *Tech for Inclusion Challenge* (Ebury × Somos F5).

> **Language convention:** code, comments, documentation, issues, commits and PRs are in English. The application itself (UI and agent answers) is in Spanish.

> Status: BDNS discovery, source-record ingestion, document preservation, change tracking, private source review and bounded-import coverage reporting are implemented. Nationwide collection and automatic extraction/verification remain pending (see the [roadmap](docs/national-roadmap.md)).

## Problem and SDGs

Agricultural and livestock farms manage aid worth thousands of euros with tools designed for the administration, not for them. Deadlines, requirements and digital procedures make them lose aid they are entitled to, or depend on intermediaries.

| SDG | How the agent contributes |
|---|---|
| **8** Decent work and economic growth | Eases access to funding for rural farms and SMEs |
| **10** Reduced inequalities | Narrows the aid-access gap in rural areas and between profiles with different digital skills |
| **17** Partnerships for the goals | Connects producers with public sources of funding (EU, State and regions) |

> TODO: back the justification with one or two real data points (a report on the rural digital divide or on reliance on paid agents).

## How it works

```
React (nginx) ──REST──► FastAPI ──► Agent (loop) ◄──► LLM with function calling (Groq)
                           │                │
                           │                ▼
                           │     Deterministic tools
                           │  search_aids · check_eligibility ·
                           │  get_application_guide · find_alternatives
                           ▼                │
                       Postgres ◄───────────┘  (aids and requirement blocks, JSONB)
```

- **The LLM decides** which tool to use and with which parameters, and writes the answer.
- **The code computes** eligibility: the LLM does not invent requirements.
- Every aid has a `source_url`, a `verified_on` date and a `reliability` level (`verified`, `extracted`, `metadata_only`).
- Only `verified` aids can produce a definitive overall eligibility result. `extracted` aids remain conditional, and `metadata_only` aids are not evaluated. Requirements marked `needs_verification` always need official confirmation.

### Tools

| Tool | When the agent uses it |
|---|---|
| `search_aids` | The user asks which aids exist or which ones they could get |
| `check_eligibility` | They ask whether they meet an aid, what is missing or what it requires |
| `get_application_guide` | They ask how to apply, where and with which documents |
| `find_alternatives` | They do not meet an aid or there are no useful results |

System prompt: [`backend/app/agent/system_prompt.md`](backend/app/agent/system_prompt.md). Tool schemas: [`backend/app/agent/tool_schemas.py`](backend/app/agent/tool_schemas.py).

## Getting started

Requirements: Docker and Docker Compose, and an API key from [Groq](https://console.groq.com).

```bash
cp .env.example .env          # and fill in LLM_API_KEY
docker compose up --build
```

Before that, `./scripts/doctor.sh` tells you whether anything is missing on your machine.

### Shortcuts with `make`

A [`Makefile`](Makefile) wraps the common commands (it needs GNU Make; on Windows use WSL or Git Bash with make). Run `make help` to see them all.

| Command | What it does |
|---|---|
| `make setup` | Creates `.env` from `.env.example` (never overwrites it) |
| `make doctor` / `make doctor-up` | Checks your machine / the running stack |
| `make up` / `make up-d` / `make down` | Starts (foreground / background) and stops the stack |
| `make reset` | Stops the stack **and deletes the database volume** |
| `make logs SERVICE=backend` | Follows the logs of one service (or all) |
| `make test` / `make test-frontend` / `make test-all` | Backend, frontend or both test suites |
| `make test-db` | Postgres integration tests (**empties** the `aids` and `blocks` tables) |
| `make seed` | Loads `backend/data/*.json` into Postgres |
| `make probe-llm` | Checks the Groq key, lists the models and tests function calling |
| `make plan-dry REPO=ORG/REPO` | Shows what the work plan would create on GitHub |

- Application: http://localhost:3000
- API and interactive docs: http://localhost:8000/docs
- Status: http://localhost:8000/api/health (shows whether the data comes from Postgres)

The first time, the backend creates the tables and **seeds** them from `backend/data/*.json` if they are empty (`SEED_ON_START=true`).

### Frontend development with hot reload

```bash
docker compose up db backend        # database and API
cd frontend && npm install && npm run dev      # http://localhost:5173 (forwards /api to :8000)
```

### Tests

```bash
docker compose run --rm backend pytest          # backend (data from Postgres if DATABASE_URL is set)
cd frontend && npm test                         # frontend logic (Node 18+)

# Postgres integration tests (they empty the aids and blocks tables of that database)
docker compose run --rm -e TEST_DATABASE_URL=postgresql://elvecino:elvecino_dev@db:5432/elvecinoquesabe backend pytest tests/test_db.py
```

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Display name of the application | `El Vecino que Sabe` |
| `LLM_API_KEY` | Groq key (or any OpenAI-compatible provider). **Never** committed to Git | — |
| `LLM_BASE_URL` | OpenAI-compatible API endpoint | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | Model with function-calling support | `openai/gpt-oss-120b` |
| `LLM_TEMPERATURE` | Temperature (low = more stable tool decisions) | `0.2` |
| `MAX_AGENT_ITERATIONS` | Maximum tool rounds per request | `4` |
| `POSTGRES_PASSWORD` | Database password (Compose) | `elvecino_dev` |
| `POSTGRES_HOST_PORT` | Host port for local Postgres access | `5432` |
| `BACKEND_HOST_PORT` | Host port for the local API | `8000` |
| `FRONTEND_HOST_PORT` | Host port for the local frontend | `3000` |
| `DATABASE_URL` | Built by Compose; if empty, data is read from the JSON files | — |
| `SEED_ON_START` | Seeds empty tables on startup | `true` |
| `ALLOWED_ORIGINS` | CORS origins (only if the frontend is on another domain) | `localhost:3000,5173` |
| `BDNS_REVIEW_TOKEN` | Shared bearer secret for the private source-review page; blank disables it | — |

> Switching provider (OpenAI, another Groq model...) only takes `LLM_BASE_URL` and `LLM_MODEL`. Check in the Groq console which models are available, that they support *tool use*, and your usage limits.

## Helper scripts

| Script | What it is for |
|---|---|
| `./scripts/doctor.sh` | Checks your machine (Git, Docker, `.env`, key, ports). With `--up` it checks the running stack. On Windows, use Git Bash or WSL |
| `docker compose run --rm backend python scripts/probe_groq.py` | Verifies the Groq key, lists the available models and tests function calling |
| `python3 backend/scripts/explore_sources.py URL…` | Probes data sources (BDNS, FEGA…) at 1 request per second, respecting `robots.txt`, and saves small samples in `docs/samples/` |
| `python3 plan/create_issues.py --repo ORG/REPO --dry-run` | Creates the labels, milestones and issues of the work plan on GitHub (see `plan/`) |
| `python3 plan/build_graph.py` | Regenerates the dependency graph from `plan/tasks.csv` and checks the plan |

Current product roadmap: [`docs/national-roadmap.md`](docs/national-roadmap.md). BDNS import coverage: [`docs/bdns-coverage.md`](docs/bdns-coverage.md). Source review: [`docs/bdns-review-workflow.md`](docs/bdns-review-workflow.md). The original event work plan is in [`plan/tasks.csv`](plan/tasks.csv) and [`plan/dependencies.md`](plan/dependencies.md). Decisions and data sources: [`docs/decisions.md`](docs/decisions.md) and [`docs/data_sources.md`](docs/data_sources.md). Spanish-to-English domain terms: [`docs/glossary.md`](docs/glossary.md). Working rules: [`CONTRIBUTING.md`](CONTRIBUTING.md).

Deployment and operations preparation: [`docs/phase-8-operations.md`](docs/phase-8-operations.md), with a managed-database production Compose template, bounded BDNS refresh runner, backup/restore guidance, monitoring checks, service-status template and correction process. A hosting provider and named operators still need to be selected before production deployment.

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | Sends the conversation and the profile; returns the answer, evaluated aids, sources and trace |
| `GET` | `/api/aids/{id}` | Detail of one aid |
| `GET` | `/api/health` | Service status and data origin |

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Tengo 300 ovejas en extensivo en Teruel. ¿Qué ayudas puedo pedir?"}],
    "profile": {"region": "Aragón", "farm_activities": ["agriculture", "livestock"], "livestock_type": ["sheep"], "production_system": "extensive"}
  }'
```

The response contains `answer`, `aids` (id, name, `overall_result`), `sources` (url, name, `verified_on`) and `trace` (the tools the agent used).

## Database (Postgres)

- Tables `aids` (one row per aid, content in `JSONB`) and `blocks` (reusable requirements such as *active farmer*). Schema in [`backend/app/db/schema.sql`](backend/app/db/schema.sql), idempotent.
- Data is **validated with Pydantic** when loaded: if something is wrong the service does not start and the message says where.
- Seed data: `backend/data/aids.json` and `blocks.json`. To (re)load them or update existing aids:

```bash
docker compose run --rm backend python -m app.db.seed
```

- Rules: every datum carries its official URL; an aid only becomes `verified` when **another person** has checked it against the original document (`verified_by`).
- Current values are **provisional** (`needs_verification`) and must not be used as advice.
- No migrations (Alembic) on purpose: the schema is small. If it changes, edit `schema.sql` and recreate the volume (`docker compose down -v`).

## Frontend

React 18 + Vite, JavaScript. Profile form, chat, and panels for **evaluated aids**, **official sources** and the **assistant's reasoning**.

```
frontend/src/
├── App.jsx · main.jsx · styles.css
├── components/   # ProfileForm, Chat, Message, ResultPanels
├── hooks/        # useChat, useLocalStorage
└── lib/          # pure, tested logic: api, profile, markdown, messages, url, storage, brand
```

- Profile validation with the same limits as the backend, and clear errors (no connection, timeout, invalid data).
- The assistant's answer is escaped before rendering (no XSS) and links only accept `http(s)`.
- Profile and conversation are kept in `localStorage`.
- In production, nginx serves the build and forwards `/api` to the backend (no CORS). If the backend is on another domain: `VITE_API_BASE`, `ALLOWED_ORIGINS` and the CSP in `frontend/nginx.conf`.
- `package-lock.json` does not exist yet: after the first `npm install`, commit it and switch `npm install` to `npm ci` in the Dockerfile and the CI.

## Continuous integration (GitHub Actions)

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push to `main` and on every pull request:

1. **Backend:** `pytest` with the data in JSON, and the integration tests against a real Postgres (service container).
2. **Frontend:** tests and `npm run build`.
3. **Docker Compose:** starts the whole stack and checks that the backend uses Postgres and that nginx serves the app and forwards `/api`.

The CI needs no secrets: the agent tests use a fake client and never call Groq.

## Structure

```
├── .github/ (workflows/ci.yml · pull_request_template.md)
├── Makefile · docker-compose.yml · .env.example · CONTRIBUTING.md
├── docs/                        # decisions, data sources and samples
├── plan/                        # tasks.csv, create_issues.py, build_graph.py and the dependency graph
├── scripts/doctor.sh
├── frontend/
│   ├── Dockerfile · nginx.conf · vite.config.js · package.json
│   ├── src/                     # React
│   └── tests/                   # node --test
└── backend/
    ├── Dockerfile · requirements.txt · pytest.ini
    ├── app/
    │   ├── main.py              # routes
    │   ├── core/                # configuration
    │   ├── models/              # profile, aid, API schemas
    │   ├── db/                  # Postgres: schema.sql, database.py, seed.py
    │   ├── data/                # sources.py (reading and validation), loader.py
    │   ├── agent/               # agent loop, prompt and tool schemas
    │   └── tools/               # requirements engine and the 4 tools
    ├── data/                    # aids.json, blocks.json (seed)
    ├── scripts/                 # probe_groq.py, explore_sources.py
    └── tests/
```

## Interaction examples

> TODO (deliverable): add at least 3 real examples with the agent's reasoning (tools called and why), copying the `trace` from the response.

## Security and limits

- Keys live in environment variables; `.env` is in `.gitignore`. Change `POSTGRES_PASSWORD` outside development.
- Inputs are validated (length, roles, types) and sanitised. Postgres only listens on `127.0.0.1`.
- The agent **reports requirements, it does not guarantee grants**. Always confirm the conditions at the official source or the local agricultural office before applying.
- Aid changes every campaign: always show `verified_on`.
- Open models on Groq may occasionally produce malformed tool calls: the backend retries up to 3 times and returns tool errors to the model so it can correct itself.

## Pending

- [ ] Try the whole stack with a real Groq key and tune the prompt from the `trace`
- [ ] Build nationwide BDNS ingestion and coverage tracking for all autonomous communities
- [ ] Verify agricultural and livestock aid records against linked official documents
- [ ] Deployment at a public URL
- [ ] Interaction examples and the supporting data point for the justification

## Team

> TODO: names and roles.
