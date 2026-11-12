# How we work

**Language:** code, comments, documentation, issues, commits and PRs are written in **English**.
Only the application itself (the UI and the agent's answers) is in Spanish.

## Branches
- `main` is protected: no direct pushes, everything goes in through a pull request.
- One short branch per task: `<type>/<task-id>-<short-description>`, for example
  `feat/F2-04-cap-records`, `fix/F1-01-backend-ci`, `docs/F0-05-groq-decision`.
- Start from an up-to-date `main`: `git switch main && git pull && git switch -c <branch>`.

## Commits: Conventional Commits
Every commit message follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<optional body: what and why>

Refs: <task-id>
```

- **Subject:** imperative mood, lower case, no final period, at most 72 characters.
  Write "add holder age validation", not "added" or "changes".
- **Footer:** `Refs: F2-04` links the commit to the task. Use `Closes #N` only in the PR.
- **One commit per logical change.** Commits that show how the agent evolved (prompt, tools) matter: the brief values them.

| Type | Use it for |
|---|---|
| `feat` | A new feature or capability |
| `fix` | A bug fix |
| `docs` | Documentation only (README, `docs/`, comments) |
| `test` | Adding or fixing tests |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | A performance improvement |
| `style` | Formatting only, no change in behaviour |
| `build` | Docker, dependencies, build tooling |
| `ci` | GitHub Actions and other CI configuration |
| `chore` | Maintenance that fits nowhere else (config, scripts, plan) |
| `revert` | Reverts a previous commit |

**Scope** is the area you touch, in lower case. Suggested: `backend`, `frontend`, `agent`, `tools`, `data`, `db`,
`api`, `docker`, `ci`, `docs`, `plan`, `scripts`, `config`, `deps`. For documents you can use their name:
`docs(decisions)`, `docs(data-sources)`.

A breaking change adds `!` after the scope and a `BREAKING CHANGE:` footer, for example
`feat(api)!: rename the profile fields`.

Examples:

```
feat(tools): add the only_open filter to search_aids
fix(docker): wait for the database before starting the backend
docs(decisions): record Groq model and usage limits
test(agent): cover the iteration limit of the agent loop
```

## Pull requests
- **The PR title is also a Conventional Commit** (`docs(decisions): record Groq model and usage limits`):
  we merge with **Squash and merge**, so the title becomes the single commit on `main`.
- Fill in the template. Link the issue with `Closes #N` (the issue number, not the task id): GitHub closes it
  automatically when the PR is merged into `main`. If the PR does not finish the task, use "Related to #N".
- At least **1 review** from someone else and a **green CI** (once the CI is stable) before merging.
- Whoever writes an aid record must not be the one who verifies it.
- Keep PRs small: one task, one PR. Delete the branch after merging.
- If `main` moved while your PR was open: `git fetch && git rebase origin/main`, then
  `git push --force-with-lease`.

## Never in Git
- API keys, passwords, `.env` files. Check before committing: `git diff --staged | grep -i "gsk_"`.
- Personal data (aid beneficiaries who are individuals).
- Large files (use small samples).

## Definition of done
- Meets the "done when" criterion of the issue.
- Has tests if it touches logic, and the CI passes.
- The affected documentation is up to date.
- A teammate has reviewed it.

## Before you start working
```bash
make doctor   # checks your machine (or ./scripts/doctor.sh)
make up       # starts the stack (or docker compose up --build)
make help     # lists every shortcut
```
