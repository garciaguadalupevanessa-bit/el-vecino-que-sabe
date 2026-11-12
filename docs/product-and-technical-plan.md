# Product and technical plan

## Product direction

Build a Spanish-language aid navigator for agricultural, livestock and mixed farms across Spain. A holding may grow crops, keep animals, or do both. The profile is progressively completed and every field is optional; crop-only holdings never need livestock data.

The service helps people discover public aid, compare their known characteristics with published requirements, identify missing information, and locate official application guidance. It is an informational proposal: the administration decides whether an application is granted.

## Trust and eligibility policy

| Aid reliability | Search and display | Eligibility | Application guidance |
|---|---|---|---|
| `verified` | May show the aid summary and its source | Python returns `met` or `not_met` only for evaluable rules with official citations. Missing or non-evaluable requirements return `unknown`; empty rule sets remain unknown. | May show checked steps; incomplete placeholder documents remain withheld. |
| `extracted` | May show provisional summary and source, clearly labelled | Overall and requirement results remain `unknown` until the rules are approved against official sources. | Withhold steps, dates and document lists until checked against the official rules. |
| `metadata_only` | Identify the aid, agency and source only | Do not evaluate requirements; return `unknown` while requirements await confirmation. | Withhold procedural details. |

Every aid record keeps its source URL, review date and reliability. A `verified` record must name a human reviewer. Data maintainers must re-check the primary public source and campaign before marking information verified. A requirement with `needs_verification` remains pending even when the farm profile appears to satisfy its provisional rule.

## Profile and matching

The shared profile covers region, province and municipality, farm activities, crops, agricultural and irrigated area, livestock species and headcount, production system, holder details, legal form, registrations and the user's goal. Existing `livestock_type` remains supported for compatibility. Missing values remain unknown; matching must not infer them.

Aid records can declare applicable `farm_activities` (`agriculture`, `livestock`, or both). The current seed aid records are broad national CAP examples, not a complete or verified catalogue. Region-specific and crop-specific aid coverage requires additional reviewed source data before the product can claim comprehensive results.

The result panels show aid reliability, applicable territory, recorded campaign and last-check date, links with their verification state, and each evaluated requirement in Spanish. They omit deadlines, documents and steps unless the aid has been verified. Coverage notes make clear that a catalog match or an empty result is not proof of complete coverage or of no aid.

## Delivery sequence

1. **Trust boundary (implemented):** keep reliability enforcement in deterministic Python tools; suppress non-verified procedural guidance; constrain metadata-only search output; prevent inferred improvement advice from unverified rules.
2. **Unified farm profile (implemented):** add optional crop, area and activity fields to the API model and UI while retaining livestock fields; allow national searches without livestock data.
3. **Regression coverage (implemented):** cover crop-only and mixed holdings, reliability-based guide limits, metadata-only display and alternatives.
4. **Data quality:** review each record against the official campaign source; record the reviewer; add verified crop and livestock aid examples with citations and test regional matching.
5. **Product validation:** interview crop-only, livestock and mixed farms; test whether profile fields are understandable and whether results communicate uncertainty clearly.
6. **Operational readiness:** decide the data refresh process and ownership, add database migrations when schema changes require them, then deploy only after source and campaign review.

## Current limitations

The supplied project is an archive without `.git` metadata, so the original staged and unstaged status cannot be recovered. Its existing aid base contains only two provisional national CAP examples and must not be treated as comprehensive advice. Backend tests require Python packages that are not installed in the available runtime.
