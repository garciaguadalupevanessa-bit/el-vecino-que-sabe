#!/usr/bin/env python3
"""Generates dependencies.mermaid and dependencies.md from tasks.csv.

Usage:  python3 plan/build_graph.py
It also checks the plan: no dependency cycles, and no task that depends on something scheduled later.
"""
import collections
import csv
import functools
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
HOURS = {"S": 1.5, "M": 3.5, "L": 7}
ORDER = {"before": 0, "event": 1, "stretch": 2}
FINAL_TASK = "F6-06"  # freeze the code and tag v1.0

rows = list(csv.DictReader((HERE / "tasks.csv").open(encoding="utf-8-sig")))
tasks = {r["id"]: r for r in rows}
deps = {i: [d for d in r["depends_on"].split(",") if d] for i, r in tasks.items()}

# --- Checks ---
state = {}
def visit(n, stack=()):
    if state.get(n) == 2:
        return
    if state.get(n) == 1:
        sys.exit(f"CYCLE: {' -> '.join(stack + (n,))}")
    state[n] = 1
    for d in deps[n]:
        visit(d, stack + (n,))
    state[n] = 2
for n in tasks:
    visit(n)

late = [(i, d) for i, r in tasks.items() for d in deps[i] if ORDER[tasks[d]["window"]] > ORDER[r["window"]]]
if late:
    sys.exit("SCHEDULING CONFLICT (a task depends on one scheduled later): " + ", ".join(f"{i}->{d}" for i, d in late))

# --- Analysis (core plan only: everything that is not stretch) ---
core = {i for i, r in tasks.items() if r["window"] != "stretch"}

@functools.lru_cache(None)
def longest(n):
    previous = [longest(d) for d in deps[n] if d in core]
    base = max(previous, key=lambda x: x[0], default=(0, []))
    return (base[0] + HOURS[tasks[n]["estimate"]], base[1] + [n])

hours, path = longest(FINAL_TASK)
blocks = collections.Counter(d for i in core for d in deps[i] if d in core)
starters = sorted(i for i in core if not [d for d in deps[i] if d in core])

# --- Mermaid ---
def short(t, n=46):
    t = t.replace('"', "'")
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"

node = lambda i: i.replace("-", "_")
css_class = lambda r: ("all" if r["owner"] == "ALL" else r["owner"].lower()) + ("s" if r["window"] == "stretch" else "")

lines = ["flowchart LR"]
phases = list(dict.fromkeys(r["phase"] for r in rows))
for k, phase in enumerate(phases):
    lines.append(f'  subgraph PHASE{k}["{phase}"]')
    for r in rows:
        if r["phase"] == phase:
            lines.append(f'    {node(r["id"])}["{r["id"]} · {short(r["title"])} ({r["owner"]})"]:::{css_class(r)}')
    lines.append("  end")
for i, ds in deps.items():
    for d in ds:
        lines.append(f"  {node(d)} --> {node(i)}")
colors = {"p1": ("#dbeafe", "#1d4ed8"), "p2": ("#dcfce7", "#15803d"), "p3": ("#fef3c7", "#b45309"),
          "p4": ("#fce7f3", "#be185d"), "all": ("#e5e7eb", "#374151")}
for k, (fill, stroke) in colors.items():
    lines.append(f"  classDef {k} fill:{fill},stroke:{stroke},color:#111827,stroke-width:2px")
    lines.append(f"  classDef {k}s fill:{fill},stroke:{stroke},color:#111827,stroke-width:1px,stroke-dasharray:5 5")
mermaid = "\n".join(lines)
(HERE / "dependencies.mermaid").write_text(mermaid + "\n", encoding="utf-8")

# --- Markdown report ---
path_rows = "\n".join(f"| {k+1} | {n} | {tasks[n]['owner']} | {tasks[n]['estimate']} | {tasks[n]['title']} |" for k, n in enumerate(path))
block_rows = "\n".join(f"| {n} | {c} | {tasks[n]['title']} |" for n, c in blocks.most_common(6))
start_rows = "\n".join(f"| {n} | {tasks[n]['owner']} | {tasks[n]['title']} |" for n in starters)
n_deps = sum(len(v) for v in deps.values())
report = f"""# Task dependencies

Generated from `tasks.csv` ({len(tasks)} tasks, {n_deps} dependencies) by `plan/build_graph.py`. An arrow `A → B` means that **B cannot be finished until A is done**.

## Graph

```mermaid
{mermaid}
```

**Legend:** colour is the owner (P1 blue, P2 green, P3 amber, P4 pink, everyone grey). Solid border = planned task (before the event or on the event day); **dashed border = stretch**.

## Critical path to v1.0 ({hours:g} h, non-stretch tasks only)

The longest chain of tasks that depend on each other up to {FINAL_TASK} (code frozen and tagged). If one of them slips, the delivery slips. Hours use rough estimates (S = 1.5 h, M = 3.5 h, L = 7 h).

| # | Task | Owner | Est. | Description |
|---|---|---|---|---|
{path_rows}

## Tasks that block the most others

| Task | Blocks | Description |
|---|---|---|
{block_rows}

## Can start right away (no dependencies)

| Task | Owner | Description |
|---|---|---|
{start_rows}
"""
(HERE / "dependencies.md").write_text(report, encoding="utf-8")

ids_defined = set(re.findall(r"^\s{4}(F\d_\d\d)\[", mermaid, re.M))
edges = re.findall(r"^\s{2}(F\d_\d\d) --> (F\d_\d\d)$", mermaid, re.M)
assert all(a in ids_defined and b in ids_defined for a, b in edges) and len(edges) == n_deps
print(f"nodes {len(ids_defined)}, edges {len(edges)}, critical path {hours:g} h: {' -> '.join(path)}")
