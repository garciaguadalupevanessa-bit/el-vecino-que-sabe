# Project decisions

Decision log. Each decision records who made it, when, and its status. Anything not yet confirmed is marked **Pending**: it is not taken for granted.

The farm profile supports agricultural, livestock and mixed holdings. Crop-only farms must not be required to provide livestock fields; fields that do not apply remain optional.

## Decisions made by the team

| Topic | Decision | Date | Status |
|---|---|---|---|
| Name | El Vecino que Sabe (repository: `elvecinoquesabe`) | | Made |
| LLM provider | Groq (OpenAI-compatible API) | | Made. Specific model: see F0-05 |
| Database | PostgreSQL | | Made |
| Frontend | React with Vite | | Made |
| Environment | Docker and Docker Compose | | Made |
| Scope | Nationwide aid for agricultural, livestock and mixed holdings: national, autonomous-community, autonomous-city and relevant local calls | 2026-11-10 | Made |
| Language | Code, internal identifiers, comments, tests and project documentation in English; UI and agent answers in Spanish | 2026-11-10 | Made |
| Discovery source | BDNS/SNPSAP is the primary nationwide discovery and ingestion source. Follow its linked official documents; consult other government pages when a document is missing, unclear or changed. | 2026-11-10 | Made |
| Coverage claim | Track coverage by territory, activity, aid category and campaign. Show review freshness and gaps; do not claim completeness from BDNS's nationwide scope alone. | 2026-11-10 | Made |
| Aid data model | Keep the aid programme separate from each individual call/campaign so dates, documents and changes cannot overwrite one another. | 2026-11-10 | Made |
| Automated checks | Automate collection, extraction, link/document checks and change detection. Machine extraction remains `extracted`; ambiguous or changed rules go to human review before `verified`. | 2026-11-10 | Made |
| User privacy | MVP has no accounts and does not request personal identifiers; ask only for farm details needed to match aid. | 2026-11-10 | Made |
| Refresh cadence | Choose the schedule after the official BDNS access guidance and API probe are checked; keep it configurable. | 2026-11-10 | Pending API probe |
| Gender angle | Dropped by the team | | **Pending confirmation with Ebury** (the brief asks for it in the system prompt) |

## Questions for Ebury (F0-07)

Owner: P1, together with the PO. Write down the answer, who answered and the date.

| # | Question | Answer | Who / when |
|---|---|---|---|
| 1 | Is a project without a gender angle accepted, given that the brief requires it in the system prompt? | Pending | |
| 2 | Does the DEGU source from the initial idea exist, or do we drop it? | Pending | |
| 3 | Which autonomous community do we prioritise? | Nationwide product. Aragón is an end-to-end validation case only. | Agreed 2026-11-10 |
| 4 | Can we bring prepared code before the event day? | Pending | |
| 5 | What exactly is the event date and how many teams take part? | Pending | |
| 6 | Are there requirements on the deployment or the repository (public or private)? | Pending | |

## Groq: key, model and limits (F0-05)

Fill this in with the real data from the Groq console and from the result of `backend/scripts/probe_groq.py`.

| Item | Value |
|---|---|
| Chosen model | `openai/gpt-oss-120b` (Groq replacement for retired `llama-3.3-70b-versatile`; tool-calling validation pending) |
| Tool-calling test result (correct / attempts) | Pending |
| Requests-per-minute limit | Pending |
| Daily limit (requests or tokens) | Pending |
| Who holds the team key and where it is stored | Pending |
| Demo strategy (reserved key, model, bulk testing) | Pending |
