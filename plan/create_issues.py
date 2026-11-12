#!/usr/bin/env python3
"""Creates labels, milestones and issues from tasks.csv and optionally adds them
to a GitHub Project. It can be run several times without creating duplicates.

Requires the GitHub CLI (gh), authenticated. To add issues to a Project: gh auth refresh -s project

Examples
  python create_issues.py --repo ORG/REPO --dry-run
  python create_issues.py --repo ORG/REPO --users P1=ana,P2=luis,P3=sara,P4=pepe --project 1 --owner ORG
  python create_issues.py --repo ORG/REPO --update      # migrate/refresh issues that already exist
"""

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


PRIORITIES = {"must": "b60205", "should": "fbca04", "stretch": "c5def5"}
ESTIMATES = {
    "S": "Small (1-2 h)",
    "M": "Medium (3-4 h)",
    "L": "Large (6-8 h)",
}
WINDOWS = {"before": "1d76db", "event": "e99695", "stretch": "c5def5"}
PEOPLE = ["P1", "P2", "P3", "P4"]

COLOR_AREA = "0e8a16"
COLOR_OWNER = "5319e7"
COLOR_EST = "bfd4f2"

# Labels created by the previous (Spanish) version of this script. --update removes them.
LEGACY_LABELS = ["ventana:antes", "ventana:dia", "ventana:stretch"]

REQUIRED_COLUMNS = [
    "id", "phase", "title", "owner", "priority", "window",
    "estimate", "area", "depends_on", "description", "done_when",
]


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def validate(rows: list[dict]) -> None:
    errors = []

    if rows:
        missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
        if missing:
            sys.exit(f"Invalid CSV: missing columns {missing}")

    ids = [r["id"] for r in rows]

    if len(ids) != len(set(ids)):
        errors.append("There are duplicated ids.")

    for r in rows:
        if r["owner"] not in PEOPLE + ["ALL"]:
            errors.append(f"{r['id']}: invalid owner ({r['owner']}).")

        if r["priority"] not in PRIORITIES:
            errors.append(f"{r['id']}: invalid priority ({r['priority']}).")

        if r["window"] not in WINDOWS:
            errors.append(f"{r['id']}: invalid window ({r['window']}).")

        if r["estimate"] not in ESTIMATES:
            errors.append(f"{r['id']}: invalid estimate ({r['estimate']}).")

        for dependency in filter(None, r["depends_on"].split(",")):
            if dependency not in ids:
                errors.append(f"{r['id']}: depends on {dependency}, which does not exist.")

    if errors:
        sys.exit("Invalid CSV:\n- " + "\n- ".join(errors))


def summary(rows: list[dict]) -> None:
    print(f"{len(rows)} tasks in {len({r['phase'] for r in rows})} phases")

    people = Counter(r["owner"] for r in rows)
    print("By owner:", ", ".join(f"{k}={v}" for k, v in sorted(people.items())))

    priorities = Counter(r["priority"] for r in rows)
    print("By priority:", ", ".join(f"{k}={v}" for k, v in priorities.items()))


class GH:

    def __init__(self, repo: str, dry: bool):
        self.repo = repo
        self.dry = dry

    def run(self, *args: str, allow_failure: bool = False) -> str:

        if self.dry:
            print("  $ gh " + " ".join(args))
            return ""

        try:
            result = subprocess.run(
                ["gh", *args],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return result.stdout.strip()

        except subprocess.CalledProcessError as e:

            error = (e.stderr or e.stdout or str(e)).strip()

            if allow_failure:
                return f"__ERROR__:{error}"

            sys.exit(f"Failure in 'gh {' '.join(args[:4])}...':\n{error}")

        except FileNotFoundError:
            sys.exit("GitHub CLI (gh) not found.")

    def json_lines(self, *args: str) -> list[dict]:

        output = self.run(*args)

        if not output:
            return []

        result = []

        for line in output.splitlines():
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                sys.exit(f"Invalid JSON returned by GitHub:\n{line}")

        return result

    def lines(self, *args: str) -> list[str]:
        output = self.run(*args)
        return [l.strip() for l in output.splitlines() if l.strip()] if output else []


def body(r: dict) -> str:

    dependencies = (
        ", ".join(x.strip() for x in r["depends_on"].split(",") if x.strip())
        or "none"
    )

    return (
        f"{r['description']}\n\n"
        f"- [ ] {r['done_when']}\n\n"
        f"**Owner:** {r['owner']} · "
        f"**Estimate:** {ESTIMATES[r['estimate']]} · "
        f"**Priority:** {r['priority']} · "
        f"**When:** {r['window']} · "
        f"**Area:** {r['area']}\n"
        f"**Depends on:** {dependencies}\n"
    )


def normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def phase_number(title: str):
    """'Phase 3 · ...' or the legacy 'Fase 3 · ...' -> 3 (None if it does not start like that)."""
    m = re.match(r"^\s*(?:phase|fase)\s+(\d+)\b", title, re.IGNORECASE)
    return int(m.group(1)) if m else None


def labels_for(r: dict) -> list[str]:
    return [
        f"priority:{r['priority']}",
        f"area:{r['area']}",
        f"owner:{r['owner']}",
        f"est:{r['estimate']}",
        f"window:{r['window']}",
    ]


# --------------------------------------------------
# MILESTONES
# --------------------------------------------------

def get_milestones(gh: GH, repo: str) -> list[dict]:

    return gh.json_lines(
        "api",
        f"repos/{repo}/milestones?state=all&per_page=100",
        "--paginate",
        "--jq",
        ".[] | @json",
    )


def ensure_milestones(gh: GH, repo: str, phases: list[str], update: bool) -> dict:

    print("\n== Milestones ==")

    existing_list = get_milestones(gh, repo)
    existing = {normalize(h["title"]): h for h in existing_list}
    result = {}

    for phase in phases:

        key = normalize(phase)

        if key in existing:
            hit = existing[key]
            result[phase] = hit
            print(f"  (reused #{hit['number']}) {phase}")
            continue

        # --update: a milestone of the same phase with an old (Spanish) title is renamed in place
        legacy = None
        if update:
            number = phase_number(phase)
            legacy = next(
                (h for h in existing_list
                 if number is not None and phase_number(h["title"]) == number
                 and normalize(h["title"]) not in {normalize(p) for p in phases}),
                None,
            )

        if legacy:
            if gh.dry:
                print(f"  (would rename #{legacy['number']} '{legacy['title']}') -> {phase}")
                result[phase] = legacy
                continue
            answer = gh.run(
                "api", "--method", "PATCH", f"repos/{repo}/milestones/{legacy['number']}",
                "-f", f"title={phase}",
                allow_failure=True,
            )
            if answer.startswith("__ERROR__:"):
                sys.exit(f"Error renaming milestone '{legacy['title']}':\n" + answer.replace("__ERROR__:", ""))
            hit = json.loads(answer)
            result[phase] = hit
            existing[key] = hit
            print(f"  (renamed #{hit['number']}) {legacy['title']} -> {phase}")
            continue

        if gh.dry:
            print(f"  (would create) {phase}")
            result[phase] = None
            continue

        answer = gh.run(
            "api", "--method", "POST", f"repos/{repo}/milestones",
            "-f", f"title={phase}",
            "-f", "state=open",
            allow_failure=True,
        )

        if answer.startswith("__ERROR__:"):

            # Recover in case the milestone was created previously.
            existing = {normalize(h["title"]): h for h in get_milestones(gh, repo)}

            if key in existing:
                hit = existing[key]
                result[phase] = hit
                print(f"  (recovered #{hit['number']}) {phase}")
                continue

            sys.exit(f"Error creating milestone '{phase}':\n" + answer.replace("__ERROR__:", ""))

        hit = json.loads(answer)
        result[phase] = hit
        existing[key] = hit
        print(f"  (created #{hit['number']}) {phase}")

    return result


# --------------------------------------------------
# ISSUES
# --------------------------------------------------

def get_issues(gh: GH, repo: str) -> list[dict]:

    return gh.json_lines(
        "issue", "list", "-R", repo,
        "--state", "all",
        "--limit", "1000",
        "--json", "title,url,number,body",
        "--jq", ".[] | @json",
    )


def find_issue(issues: list[dict], identifier: str):

    pattern = re.compile(rf"^\[{re.escape(identifier)}\](?:\s|$)", re.IGNORECASE)

    for issue in issues:
        if pattern.match(issue["title"]):
            return issue

    return None


def create_issue(gh: GH, repo: str, r: dict, users: dict) -> str:

    title = f"[{r['id']}] {r['title']}"

    args = [
        "issue", "create", "-R", repo,
        "--title", title,
        "--body", body(r),
        "--milestone", r["phase"],
    ]

    for label in labels_for(r):
        args += ["--label", label]

    if r["owner"] == "ALL":
        assignees = list(dict.fromkeys(users.values()))
    else:
        user = users.get(r["owner"])
        assignees = [user] if user else []

    for user in assignees:
        args += ["--assignee", user]

    output = gh.run(*args)

    if gh.dry:
        return ""

    urls = re.findall(r"https://github\.com/\S+/issues/\d+", output)

    if not urls:
        sys.exit(f"Could not get the issue URL:\n{output}")

    return urls[-1]


def update_issue(gh: GH, repo: str, issue: dict, r: dict, repo_labels: set) -> bool:
    """Refreshes title, body, milestone and labels of an existing issue. Returns True on success."""

    new_body = body(r)
    # Keep the "done" tick if someone already ticked the checkbox
    if "- [x]" in (issue.get("body") or "").lower():
        new_body = new_body.replace("- [ ]", "- [x]", 1)

    args = [
        "issue", "edit", str(issue["number"]), "-R", repo,
        "--title", f"[{r['id']}] {r['title']}",
        "--body", new_body,
        "--milestone", r["phase"],
    ]

    for label in labels_for(r):
        args += ["--add-label", label]

    for legacy in LEGACY_LABELS:
        if legacy in repo_labels:
            args += ["--remove-label", legacy]

    result = gh.run(*args, allow_failure=True)

    if result.startswith("__ERROR__:"):
        print("    FAILED: " + result.replace("__ERROR__:", "").splitlines()[0])
        return False

    return True


# --------------------------------------------------
# GITHUB PROJECT
# --------------------------------------------------

def add_to_project(gh: GH, project: int, owner: str, url: str):

    result = gh.run(
        "project", "item-add", str(project),
        "--owner", owner,
        "--url", url,
        allow_failure=True,
    )

    if result.startswith("__ERROR__:"):

        error = result.lower()

        if (
            "already exists" in error
            or "content already exists" in error
            or "already in the project" in error
        ):
            print("    (already in the Project)")
            return

        sys.exit(f"Error adding {url} to the Project:\n" + result.replace("__ERROR__:", ""))


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main(argv=None):

    parser = argparse.ArgumentParser(
        description="Creates labels, milestones and issues from tasks.csv (idempotent).")

    parser.add_argument("--repo", required=True, help="OWNER/REPO")
    parser.add_argument("--csv", default=str(Path(__file__).with_name("tasks.csv")))
    parser.add_argument("--users", default="", help="Map of people to GitHub users: P1=ana,P2=luis,...")
    parser.add_argument("--project", type=int, help="Number of the GitHub Project to add the issues to")
    parser.add_argument("--owner", help="Owner (user or organisation) of the Project")
    parser.add_argument("--update", action="store_true",
                        help="Also refresh issues that already exist (title, body, milestone, labels) and "
                             "rename old milestones. It overwrites the issue bodies; ticked checkboxes are kept.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")

    args = parser.parse_args(argv)

    if not re.fullmatch(r"[^/\s]+/[^/\s]+", args.repo):
        parser.error("--repo must have the format OWNER/REPO.")

    if args.project and not args.owner:
        parser.error("--project requires --owner.")

    rows = read_rows(Path(args.csv))

    validate(rows)
    summary(rows)

    users = dict(p.split("=", 1) for p in args.users.split(",") if "=" in p)

    gh = GH(args.repo, args.dry_run)

    # LABELS

    print("\n== Labels ==")

    labels = {f"priority:{p}": c for p, c in PRIORITIES.items()}
    labels.update({f"area:{x}": COLOR_AREA for x in sorted({r["area"] for r in rows})})
    labels.update({f"owner:{p}": COLOR_OWNER for p in PEOPLE + ["ALL"]})
    labels.update({f"est:{e}": COLOR_EST for e in ESTIMATES})
    labels.update({f"window:{v}": c for v, c in WINDOWS.items()})

    for name, color in labels.items():
        gh.run("label", "create", name, "--color", color, "--force", "-R", args.repo)

    # MILESTONES

    phases = list(dict.fromkeys(r["phase"] for r in rows))
    ensure_milestones(gh, args.repo, phases, args.update)

    # ISSUES

    print("\n== Issues ==")

    issues = get_issues(gh, args.repo)
    repo_labels = set(gh.lines("label", "list", "-R", args.repo, "--limit", "500",
                               "--json", "name", "--jq", ".[].name")) if args.update else set()

    created = reused = updated = failed = project_ok = 0

    for r in rows:

        identifier = r["id"]
        title = f"[{identifier}] {r['title']}"

        print(f"\n- {title} ({r['owner']})")

        existing = find_issue(issues, identifier)

        if existing:

            url = existing.get("url", "")
            number = existing.get("number")

            reused += 1
            print(f"    (reused #{number})")

            if args.update:
                if update_issue(gh, args.repo, existing, r, repo_labels):
                    updated += 1
                    print("    (updated)")
                else:
                    failed += 1

        else:

            url = create_issue(gh, args.repo, r, users)

            if gh.dry:
                continue

            created += 1

            print(f"    (created) {url}")

            issues.append({
                "title": title,
                "url": url,
                "number": int(url.rstrip("/").split("/")[-1]),
                "body": "",
            })

        # IMPORTANT: reused issues are also added to the Project.

        if args.project and url:
            add_to_project(gh, args.project, args.owner, url)
            project_ok += 1

    # Old Spanish labels are deleted only after every issue has been moved to the new ones
    if args.update:
        print("\n== Legacy labels ==")
        for legacy in LEGACY_LABELS:
            if legacy in repo_labels or args.dry_run:
                if failed:
                    print(f"  (kept {legacy}: some issues failed to update)")
                    continue
                gh.run("label", "delete", legacy, "--yes", "-R", args.repo, allow_failure=True)
                print(f"  ({'would delete' if args.dry_run else 'deleted'}) {legacy}")

    print("\n========== SUMMARY ==========")
    print(f"Issues created: {created}")
    print(f"Issues reused: {reused}")

    if args.update:
        print(f"Issues updated: {updated}")
        print(f"Issues that failed to update: {failed}")

    if args.project:
        print(f"Issues processed for the Project: {project_ok}")

    if args.dry_run:
        print("\nDry run finished.")
    else:
        print("\nDone.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
