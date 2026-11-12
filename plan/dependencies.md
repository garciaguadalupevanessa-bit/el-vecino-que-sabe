# Task dependencies

Generated from `tasks.csv` (57 tasks, 67 dependencies) by `plan/build_graph.py`. An arrow `A → B` means that **B cannot be finished until A is done**.

## Graph

```mermaid
flowchart LR
  subgraph PHASE0["Phase 0 · Setup"]
    F0_01["F0-01 · Create the repository and add the team (P3)"]:::p3
    F0_02["F0-02 · Push the project skeleton and review the READ… (P3)"]:::p3
    F0_03["F0-03 · Create the GitHub Project (board) with status… (P4)"]:::p4
    F0_04["F0-04 · Agree on working conventions (CONTRIBUTING.md) (P4)"]:::p4s
    F0_05["F0-05 · Create the team's Groq key and document the l… (P1)"]:::p1
    F0_06["F0-06 · Verify the prepared Docker stack on every mac… (ALL)"]:::all
    F0_07["F0-07 · Confirm with Ebury: gender angle, DEGU source… (P1)"]:::p1
    F0_08["F0-08 · Probe access to BDNS and FEGA (API, downloads… (P2)"]:::p2
  end
  subgraph PHASE1["Phase 1 · Technical foundation"]
    F1_01["F1-01 · First push: fix the backend CI failures (P3)"]:::p3
    F1_02["F1-02 · Run and fix the Postgres integration tests (P3)"]:::p3
    F1_03["F1-03 · Fix the frontend build and tests and generate… (P4)"]:::p4
    F1_04["F1-04 · Make the Docker Compose smoke test pass in CI (P3)"]:::p3
    F1_05["F1-05 · First real Groq call: verify function calling (P1)"]:::p1
  end
  subgraph PHASE2["Phase 2 · Data and content"]
    F2_01["F2-01 · Define the list of candidate aids (6-8 to imp… (P2)"]:::p2
    F2_02["F2-02 · Shared sheet template and export script to ai… (P2)"]:::p2
    F2_03["F2-03 · Reusable blocks: active farmer, conditionalit… (P1)"]:::p1
    F2_04["F2-04 · Aid records: CAP direct payments and eco-sche… (P2)"]:::p2
    F2_05["F2-05 · Aid records: livestock coupled support by liv… (P4)"]:::p4
    F2_06["F2-06 · Aid records: young farmers start-up and moder… (P2)"]:::p2s
    F2_07["F2-07 · Aid records: agricultural insurance and anima… (P2)"]:::p2s
    F2_08["F2-08 · Aid records: the chosen autonomous community (P2)"]:::p2s
    F2_09["F2-09 · Cross-verification, batch 1 (CAP) (P3)"]:::p3
    F2_10["F2-10 · Cross-verification, batch 2 (livestock aids) (P2)"]:::p2
    F2_11["F2-11 · Load the base into Postgres and review /api/a… (P2)"]:::p2
  end
  subgraph PHASE3["Phase 3 · Agent and prompt"]
    F3_01["F3-01 · Define 8-10 agent evaluation cases (P1)"]:::p1
    F3_02["F3-02 · Evaluation script against the backend (P1)"]:::p1
    F3_03["F3-03 · Tune the system prompt with real cases and ex… (P1)"]:::p1
    F3_04["F3-04 · Improve tool descriptions and colloquial-lang… (P1)"]:::p1s
    F3_05["F3-05 · Improve search_aids ranking with the real base (P3)"]:::p3s
    F3_06["F3-06 · Adapt find_alternatives and get_application_g… (P3)"]:::p3s
    F3_07["F3-07 · Extend /api/chat with requirements and missin… (P3)"]:::p3s
    F3_08["F3-08 · Test Groq's limits and friendly error messages (P1)"]:::p1
    F3_09["F3-09 · Manipulation tests (prompt injection) and out… (P3)"]:::p3
  end
  subgraph PHASE4["Phase 4 · Frontend and UX"]
    F4_01["F4-01 · Review the app in the browser with the real b… (P4)"]:::p4
    F4_02["F4-02 · Show requirement details per aid (met, missin… (P4)"]:::p4s
    F4_03["F4-03 · Responsive design and accessibility (mobile,… (P4)"]:::p4s
    F4_04["F4-04 · Loading and error states; test offline and ti… (P4)"]:::p4s
    F4_05["F4-05 · Review the UI texts for plain language with t… (P4)"]:::p4s
    F4_06["F4-06 · React component tests (P4)"]:::p4s
  end
  subgraph PHASE5["Phase 5 · Deployment and documentation"]
    F5_01["F5-01 · Choose a platform with Docker support and cre… (P3)"]:::p3
    F5_02["F5-02 · Deploy the prepared containers (backend, fron… (P3)"]:::p3
    F5_03["F5-03 · Deployment pipeline with GitHub Actions (P3)"]:::p3s
    F5_04["F5-04 · Rate limiting and security review (P3)"]:::p3s
    F5_05["F5-05 · Final README with the SDG justification and a… (P4)"]:::p4
    F5_06["F5-06 · Find a real supporting data point (rural digi… (P2)"]:::p2
    F5_07["F5-07 · Technical documentation: endpoints, tools, pr… (P2)"]:::p2
  end
  subgraph PHASE6["Phase 6 · Event-day preparation"]
    F6_01["F6-01 · Event-day timeboxing plan (ALL)"]:::all
    F6_02["F6-02 · Demo script (3 cases) and sample data (P4)"]:::p4
    F6_03["F6-03 · Presentation: problem, SDGs, solution, archit… (P4)"]:::p4
    F6_04["F6-04 · One timed demo rehearsal (ALL)"]:::all
    F6_05["F6-05 · Plan B: screenshots or video of the demo and… (P4)"]:::p4s
    F6_06["F6-06 · Freeze the code and tag v1.0 before the prese… (P3)"]:::p3
  end
  subgraph PHASE7["Phase 7 · Stretch"]
    F7_01["F7-01 · BDNS ingestion script into Postgres (P2)"]:::p2s
    F7_02["F7-02 · Model budgeted, granted and paid amounts (P2)"]:::p2s
    F7_03["F7-03 · distribution_analyzer tool (P3)"]:::p3s
    F7_04["F7-04 · Text search over the regulatory rules (P1)"]:::p1s
    F7_05["F7-05 · Distribution charts in the frontend (P4)"]:::p4s
  end
  F0_01 --> F0_02
  F0_01 --> F0_03
  F0_01 --> F0_04
  F0_02 --> F0_06
  F0_05 --> F0_06
  F0_02 --> F1_01
  F1_01 --> F1_02
  F0_02 --> F1_03
  F1_01 --> F1_04
  F1_03 --> F1_04
  F0_05 --> F1_05
  F1_01 --> F1_05
  F0_07 --> F2_01
  F0_08 --> F2_01
  F2_01 --> F2_03
  F2_02 --> F2_04
  F2_03 --> F2_04
  F2_02 --> F2_05
  F2_03 --> F2_05
  F2_02 --> F2_06
  F2_03 --> F2_06
  F2_02 --> F2_07
  F0_07 --> F2_08
  F2_02 --> F2_08
  F2_04 --> F2_09
  F2_05 --> F2_09
  F2_05 --> F2_10
  F2_09 --> F2_11
  F2_10 --> F2_11
  F2_01 --> F3_01
  F1_05 --> F3_02
  F3_01 --> F3_02
  F2_11 --> F3_03
  F3_02 --> F3_03
  F3_03 --> F3_04
  F2_11 --> F3_05
  F2_11 --> F3_06
  F1_01 --> F3_07
  F1_05 --> F3_08
  F3_03 --> F3_09
  F1_03 --> F4_01
  F1_05 --> F4_01
  F3_07 --> F4_02
  F4_01 --> F4_03
  F4_01 --> F4_04
  F4_01 --> F4_05
  F4_02 --> F4_06
  F1_04 --> F5_01
  F5_01 --> F5_02
  F1_04 --> F5_02
  F5_02 --> F5_04
  F5_06 --> F5_05
  F3_03 --> F5_07
  F1_05 --> F5_07
  F1_05 --> F6_01
  F1_05 --> F6_02
  F6_02 --> F6_03
  F5_02 --> F6_04
  F6_03 --> F6_04
  F3_03 --> F6_04
  F6_04 --> F6_06
  F0_08 --> F7_01
  F2_11 --> F7_01
  F7_01 --> F7_02
  F7_01 --> F7_03
  F7_01 --> F7_04
  F7_03 --> F7_05
  classDef p1 fill:#dbeafe,stroke:#1d4ed8,color:#111827,stroke-width:2px
  classDef p1s fill:#dbeafe,stroke:#1d4ed8,color:#111827,stroke-width:1px,stroke-dasharray:5 5
  classDef p2 fill:#dcfce7,stroke:#15803d,color:#111827,stroke-width:2px
  classDef p2s fill:#dcfce7,stroke:#15803d,color:#111827,stroke-width:1px,stroke-dasharray:5 5
  classDef p3 fill:#fef3c7,stroke:#b45309,color:#111827,stroke-width:2px
  classDef p3s fill:#fef3c7,stroke:#b45309,color:#111827,stroke-width:1px,stroke-dasharray:5 5
  classDef p4 fill:#fce7f3,stroke:#be185d,color:#111827,stroke-width:2px
  classDef p4s fill:#fce7f3,stroke:#be185d,color:#111827,stroke-width:1px,stroke-dasharray:5 5
  classDef all fill:#e5e7eb,stroke:#374151,color:#111827,stroke-width:2px
  classDef alls fill:#e5e7eb,stroke:#374151,color:#111827,stroke-width:1px,stroke-dasharray:5 5
```

**Legend:** colour is the owner (P1 blue, P2 green, P3 amber, P4 pink, everyone grey). Solid border = planned task (before the event or on the event day); **dashed border = stretch**.

## Critical path to v1.0 (23.5 h, non-stretch tasks only)

The longest chain of tasks that depend on each other up to F6-06 (code frozen and tagged). If one of them slips, the delivery slips. Hours use rough estimates (S = 1.5 h, M = 3.5 h, L = 7 h).

| # | Task | Owner | Est. | Description |
|---|---|---|---|---|
| 1 | F0-08 | P2 | M | Probe access to BDNS and FEGA (API, downloads and limits) |
| 2 | F2-01 | P2 | S | Define the list of candidate aids (6-8 to implement) |
| 3 | F2-03 | P1 | M | Reusable blocks: active farmer, conditionality and young farmer |
| 4 | F2-04 | P2 | M | Aid records: CAP direct payments and eco-schemes |
| 5 | F2-09 | P3 | M | Cross-verification, batch 1 (CAP) |
| 6 | F2-11 | P2 | S | Load the base into Postgres and review /api/aids |
| 7 | F3-03 | P1 | M | Tune the system prompt with real cases and examples with real aids |
| 8 | F6-04 | ALL | S | One timed demo rehearsal |
| 9 | F6-06 | P3 | S | Freeze the code and tag v1.0 before the presentations |

## Tasks that block the most others

| Task | Blocks | Description |
|---|---|---|
| F1-05 | 6 | First real Groq call: verify function calling |
| F0-02 | 3 | Push the project skeleton and review the README |
| F3-03 | 3 | Tune the system prompt with real cases and examples with real aids |
| F1-01 | 3 | First push: fix the backend CI failures |
| F0-05 | 2 | Create the team's Groq key and document the limits |
| F0-01 | 2 | Create the repository and add the team |

## Can start right away (no dependencies)

| Task | Owner | Description |
|---|---|---|
| F0-01 | P3 | Create the repository and add the team |
| F0-05 | P1 | Create the team's Groq key and document the limits |
| F0-07 | P1 | Confirm with Ebury: gender angle, DEGU source and priority region |
| F0-08 | P2 | Probe access to BDNS and FEGA (API, downloads and limits) |
| F2-02 | P2 | Shared sheet template and export script to aids.json |
| F5-06 | P2 | Find a real supporting data point (rural digital divide or reliance on paid agents) |
